# as root
# Verify that the script is run
# if (($EUID != 0)); then
# echo "Please run this script as root!"
# exit
# fi

# ----- Project Variables ----- #
TIMEZONE=America/Chicago
BASH_PATH=$(which bash)
DOCKER_PATH=$(which docker)
PROJECT_PATH=$(pwd)
CRONFILE_NAME=cronfile
CONFIG_PATH=$PROJECT_PATH/config
ISURI_PATH=$CONFIG_PATH/item_server_url.txt
CLOUDFLARE_TUNNEL_TOKEN_PATH=$CONFIG_PATH/cf_tunnel_token.txt

# ----- Backend ----- #
# Normal crawl vars
# By default, crawl 10 times
# starting at 2:00 am everyday.
NUM_CRAWLS_PER_DAY=10
CRAWL_START_HOUR=2
CRAWL_START_MINUTE=0
BACKEND_COMPOSE_PATH=$PROJECT_PATH/compose.backend.yaml
CRAWLER_SERVICE=rc_crawler
LEAF_EXTRACTOR_SERVICE=leaf_extractor

# Leaf extraction vars
# By default, crawl on Sunday, 12:00 am
# every week.
LEAF_EXTRACTION_DAY=0
LEAF_EXTRACTION_START_HOUR=0
LEAF_EXTRACTION_START_MINUTE=0

# ----- Frontend ----- #
# By default, start the frontend server
# at 6:45 am.
FRONTEND_COMPOSE_PATH=$PROJECT_PATH/compose.frontend.yaml
FRONTEND_START_HOUR=6
FRONTEND_START_MINUTE=45

# By default, end the frontend server
# at 10:30 pm.
FRONTEND_STOP_HOUR=22
FRONTEND_STOP_MINUTE=30

# Set timezone
timedatectl set-timezone $TIMEZONE

# Create the cronfile
# and append our scheduled tasks to it
echo "Making temporary cronfile..."
touch $CRONFILE_NAME

# Backend leaf extraction
# and code synchronization
echo "Instructing crontab to initiate crawl $NUM_CRAWLS_PER_DAY times per day" \
  "starting at $CRAWL_START_HOUR:$CRAWL_START_MINUTE"
echo "$CRAWL_START_MINUTE $CRAWL_START_HOUR * * *" \
  "$DOCKER_PATH compose -f $BACKEND_COMPOSE_PATH run $LEAF_EXTRACTOR_SERVICE" >$CRONFILE_NAME

# Backend crawl. Perform
# for the predesignated amount of times
echo "Instructing crontab to extract leaves on day $LEAF_EXTRACTION_DAY" \
  "starting at $LEAF_EXTRACTION_START_HOUR:$LEAF_EXTRACTION_START_MINUTE"
echo "$LEAF_EXTRACTION_START_MINUTE $LEAF_EXTRACTION_START_HOUR * * $LEAF_EXTRACTION_DAY" \
  "$BASH_PATH -c \"for i in {1..$NUM_CRAWLS_PER_DAY}:; do" \
  "$DOCKER_PATH compose -f $BACKEND_COMPOSE_PATH run $CRAWLER_SERVICE; done\"" >>$CRONFILE_NAME

# Daemonize the frontend server
# at designated time
echo "Instructing crontab to fireup server everyday" \
  "from $FRONTEND_START_HOUR:$FRONTEND_START_MINUTE"
echo "$FRONTEND_START_MINUTE $FRONTEND_START_HOUR * * *" \
  "$DOCKER_PATH compose -f $FRONTEND_COMPOSE_PATH up -d" >>$CRONFILE_NAME

# Stop the frontend server
# at designated time
echo "Instructing crontab to stop server everday" \
  "at $FRONTEND_STOP_HOUR:$FRONTEND_STOP_MINUTE"
echo "$FRONTEND_STOP_MINUTE $FRONTEND_STOP_HOUR * * *" \
  "$DOCKER_PATH compose -f $FRONTEND_COMPOSE_PATH down" >>$CRONFILE_NAME

# Append this cronfile's contents to
# the current user's crontab
crontab -l 2>/dev/null | cat - $CRONFILE_NAME | crontab -
echo "Crontab successfully installed"
echo "Removing temporary cronfile..."
rm $CRONFILE_NAME

# Touch files that should be used for secrets
echo "Touching secret files..."
touch $ISURI_PATH && echo "ISURI PATH: $ISURI_PATH"
touch $CLOUDFLARE_TUNNEL_TOKEN_PATH && echo "CF TUNNEL PATH: $CLOUDFLARE_TUNNEL_TOKEN_PATH"
