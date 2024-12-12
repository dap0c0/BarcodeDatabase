import urllib.parse
from re import error
from abc import ABC, abstractmethod
from twisted.internet.defer import Deferred
from twisted.internet import ssl
from PatternExtractor import PatternExtractor
from HTTPResponse import HTTPResponse
from SimpleHTTPFactory import SimpleHTTPFactory
from Queue import LLQueue
from FileInterface import LinkWriter

class URLError(error):
    pass

class WebCrawler(ABC):
    # Basic hyperlink pattern: scheme://domain.tld/example/path
    HYPERLINK_REGEX_PATTERN = r"(?:\w+://)(?:[a-zA-Z0-9-_]+\.)+(?:[a-z]*)(?:/[a-zA-Z0-9-_]+)*/?"

    def __init__(self, seed: str, results_file: str, sleep: float | int = 0):
        assert isinstance(seed, str)
        assert isinstance(results_file, str)
        assert isinstance(sleep, float) or isinstance(sleep, int)
        assert sleep >= 0
        self.seed = seed
        self.file_interface = LinkWriter(results_file)
        self.sleep = sleep
        self.http_responses = {} # Each url will contain a list of links

        self._url_queue = LLQueue()
        self._extractor = PatternExtractor()
        self._explored_links = set() # Assure that no link is traversed twice

    @abstractmethod
    def crawl(self, debug: bool=False, url_criteria: str=None):
        pass

    def _extract_links(self, input: str, url_criteria: str=None):
        ''' Extract all links from the input string and
            return a list of all matches.'''
        assert isinstance(input, str)

        if not url_criteria:
            self._extractor.set_pattern(WebCrawler.HYPERLINK_REGEX_PATTERN)

        else:
            self._extractor.set_pattern(url_criteria)

        return self._extractor.get_matches(input)

    def _is_valid_url(self, url: str):
        ''' Verify that the supplied url follows the
            format of HYPERLINK_REGEX_PATTERN'''
        assert isinstance(url, str)
        
        if not self._extract_links(url):
            return False

        return True

    def shutdown(self):
        ''' Close the file_interface and stop the reactor.'''
        from twisted.internet import reactor
        self.file_interface.close()
        reactor.stop()

class TwistedWebCrawler(WebCrawler):
    HTTP_PORT = 40
    HTTPS_PORT = 443
    MAX_TO_DEQUEUE = 1000

    def _promise_http(self, url: str, debug: bool=False) -> Deferred:
        ''' Connect to the server and delegate
            http extraction to the HTTP Factory.

            Returns a deferred.'''
        if self._is_valid_url(url):
            d = Deferred()

            # Get relevant information from the url
            parsed = urllib.parse.urlparse(url)
            scheme = parsed.scheme
            host = parsed.netloc
            path = parsed.path
            query = parsed.query

            if len(path) == 0:
                path = "/"

            # Allow factory to bridge between main code and the reactor loop.
            # The bridge is primarily through callbacks and errbacks added
            # to the deferred at runtime.
            if len(query) == 0:
                factory = SimpleHTTPFactory(d, url, scheme, host, path, debug, None)

            else:
                factory = SimpleHTTPFactory(d, url, scheme, host, path, debug, query)

            from twisted.internet import reactor

            # Connect to the appropriate port.
            # Upon connection, the factory will delegate work
            # to its protocol and return results through deferred.
            if scheme == "http":
                reactor.connectTCP(host, TwistedWebCrawler.HTTP_PORT, factory)

            elif scheme == "https":
                reactor.connectSSL(host, TwistedWebCrawler.HTTPS_PORT, factory, ssl.ClientContextFactory())

            # Prevent redundant link traversal
            self._explored_links.add(url)
            return d

    def crawl(self, debug: bool=False, url_criteria: str=None, max_to_dequeue: int=MAX_TO_DEQUEUE):
        ''' Start crawling from the presupplied self.seed url.
        If any url_criteria was supplied, only crawl for a certain regex url.

        Write all links extracted to self.results_file at runtime.'''
        assert isinstance(debug, bool)
        assert isinstance(url_criteria, str) or not url_criteria
        
        # Callback #1: protocol successfully received all HTTP data.
        # Attempt to extract all links from the HTTP content.
        def extract_links_http(http_response: HTTPResponse):
            if url_criteria:
                links = self._extract_links(str(http_response), url_criteria)

            else:
                links = self._extract_links(str(http_response), WebCrawler.HYPERLINK_REGEX_PATTERN)

            return links

        # Callback: all links were successfully extracted. For debugging,
        # if enabled, print all links that were extracted.
        def display_links(links: list):
            if debug:
                print(f"<---- {len(links)} links extracted! ---->")

                for link in links:
                    print(link)

            return links

        # Callback: write all links to the file via
        # the file interface. Propagate all links for enqueuing
        # in the next callback.
        def write_links(links: list):
            for link in links:
                assert isinstance(link, str)
                self.file_interface.append(link)

            return links

        # Callback: all links were successfully extracted. Enqueue them
        # for requests. Pass the number of urls to dequeue to the next callback.
        def enqueue_links(links: list):
            for link in links:
                print(f"Enqueued {link}")
                self._url_queue.enqueue(link)

            if len(self._url_queue) < max_to_dequeue:
                return len(self._url_queue)

            else:
                return max_to_dequeue

        # Callback: all links were successfully enqueued.
        # Promise http for all of them.
        def promise_http_multiple(num_to_request: int):
            url_mutable = [None]

            for i in range(num_to_request):
                url_mutable[0] = self._url_queue.dequeue()
                react(url_mutable)

        # Errback #1: Propogate the KeyboardInterrupt to the shutdown errback
        def keyboard_interrupt_caught(ki: KeyboardInterrupt):
            if debug:
                print("Keyboard interrupt caught.")

            return ki

        # Errback #2: For any given error that's not redirected to its respective
        # callback, end the program.
        def shutdown(e: error):
            self.shutdown()

            if debug:
                print("Shutting down crawler.")

        def react(curr_url_mutable: list):
            ''' Promise http for the url in the mutable list.'''
            assert isinstance(curr_url_mutable, list)
            assert len(curr_url_mutable) == 1
            assert isinstance(curr_url_mutable[0], str)
            d = self._promise_http(curr_url_mutable[0], debug)
            d.addCallback(extract_links_http)
            d.addCallback(display_links)
            d.addCallback(write_links)
            d.addCallback(enqueue_links)
            d.addCallback(promise_http_multiple)
            d.addErrback(keyboard_interrupt_caught)
            d.addErrback(shutdown)

        # Check whether the url_criteria is valid when necessary
        if url_criteria and not self._is_valid_url(url_criteria):
                raise URLError(f"The url_criteria {url_criteria} doesn't follow URL standards.")

        # Kickoff processing with the seed url
        print(f"Seed is {self.seed}")
        self._url_queue.enqueue(self.seed)
        curr_url = self._url_queue.dequeue() # a bit redundant, but thats ok
        curr_url_mutable = [curr_url]

        from twisted.internet import reactor
        reactor.callWhenRunning(react, curr_url_mutable)
        reactor.run()
