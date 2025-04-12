{ pkgs }:

pkgs.mkShell {
  buildInputs = [
    pkgs.python311
    pkgs.python311Packages.flask
    pkgs.python311Packages.flask_cors
    pkgs.python311Packages.google-api-python-client
    pkgs.python311Packages.google-auth
    pkgs.python311Packages.google-auth-httplib2
    pkgs.python311Packages.google-auth-oauthlib
    pkgs.python311Packages.requests
    pkgs.python311Packages.psutil
  ];
}
