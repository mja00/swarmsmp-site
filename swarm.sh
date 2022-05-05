# We want to get the first argument
first_arg=$1

function prune_images {
  echo "Pruning the docker images"
  docker image prune -f
}

# If the first arg is update, we want to git pull the repo
if [ "$first_arg" = "update" ]; then
  echo "Updating the repo"
  git pull
  exit 0
fi

# If the first arg is build or deploy, we want to build the docker image
if [ "$first_arg" = "build" ] || [ "$first_arg" = "deploy" ]; then
  echo "Building the docker image"
  docker-compose -f docker-compose.prod.yml build
  prune_images
  exit 0
fi

# If the first arg is up, we want to start the docker containers
if [ "$first_arg" = "up" ]; then
  echo "Starting the docker containers"
  docker-compose -f docker-compose.prod.yml up -d
  exit 0
fi

# If the first arg is down, we want to stop the docker containers
if [ "$first_arg" = "down" ]; then
  echo "Stopping the docker containers"
  docker-compose -f docker-compose.prod.yml down
  exit 0
fi

# If the first arg is restart, we want to restart the docker containers
if [ "$first_arg" = "restart" ]; then
  echo "Restarting the docker containers"
  docker-compose -f docker-compose.prod.yml restart
  exit 0
fi

# If the first arg is migrate, we want to run the migrations
if [ "$first_arg" = "migrate" ]; then
  echo "Running the migrations"
  docker-compose -f docker-compose.prod.yml exec web flask db upgrade
  exit 0
fi

# If the first arg is full_update, we want to git pull, build, start, and migrate
if [ "$first_arg" = "full_update" ]; then
  echo "Full update"
  echo "Updating the repo"
  git pull
  echo "Building the docker image"
  docker-compose -f docker-compose.prod.yml build
  echo "Starting the docker containers"
  docker-compose -f docker-compose.prod.yml up -d
  echo "Running the migrations"
  docker-compose -f docker-compose.prod.yml exec web flask db upgrade
  prune_images
  exit 0
fi

# If the first arg is upgrade, pull, build and start the containers
if [ "$first_arg" = "upgrade" ]; then
  echo "Upgrading the docker containers"
  echo "Updating the repo"
  git pull
  echo "Building the docker image"
  docker-compose -f docker-compose.prod.yml build
  echo "Starting the docker containers"
  docker-compose -f docker-compose.prod.yml up -d
  prune_images
  exit 0
fi
