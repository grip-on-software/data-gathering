Server certificates
===================

Store server HTTP over SSL certificates in this directory to provide them to 
the data gathering agent Docker images.

Use OpenSSL on the server to generate the SSL certificates:

- Generate: `openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem 
  -nodes -days 1366`
- Verify: `openssl x509 -in cert.pem -text -noout`
- Create private host certificate: `cat cert.pem key.pem > host.pem`. Save this 
  in the configuration directory for your server with rights for only the 
  server uid.
- Copy over cert.pem to this directory to add it to the Docker image.
- Use `docker-compose.yml` or `docker build --build-arg` to set the environment 
  variables `SSH_HOST` and `SSH_HTTPS_CERT` to the server hostname and the path 
  to the certificate.
