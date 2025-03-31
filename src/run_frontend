from frontend.FrontEndServer import FrontEndServer
import argparse

if __name__ == "__main__":
    # Get the mongodb endpoint for our item server.
    parser = argparse.ArgumentParser()
    parser.add_argument("--item_server_uri", "-isuri", action="store", type=str, dest="item_server_uri", required=True)
    args = parser.parse_args()

    # Initialize frontend and serve it
    fe_server = FrontEndServer(args.item_server_uri)
    fe_server.serve()
