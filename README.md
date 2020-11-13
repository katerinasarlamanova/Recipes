This is a web application for recipes

To build the image use  the command:
docker build -t <image name> .

To run the container use the command:
docker run -d -p 5000:5000 -v <path to app.py file>:/app --name <container name> <image name>