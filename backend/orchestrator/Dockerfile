# Use the official lightweight Python 3.11 image.
FROM python:3.11-slim

# Set the working directory in the container.
WORKDIR /app

# Copy the requirements file into the container.
COPY requirements.txt .

# Install the dependencies. Note: We use the production-ready Gunicorn server.
RUN pip install --no-cache-dir -r requirements.txt && pip install gunicorn

# Copy the rest of the application's code into the container.
COPY . .

# Expose the port that Gunicorn will run on.
EXPOSE 8080

# Command to run the application using Gunicorn.
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "main:app"]