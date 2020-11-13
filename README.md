This is a web application for recipes


To build the image use  the command:

docker build -t image_name .


To run the container use the command:

docker run -d -p 5000:5000 -v path_to_file:/app --name container_name image_name
