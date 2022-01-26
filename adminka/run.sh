#!/bin/sh
sudo systemctl stop flaskapp && sudo systemctl daemon-reload && sudo systemctl start flaskapp && sudo systemctl enable flaskapp && sudo systemctl status flaskapp
