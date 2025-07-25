#!/bin/bash
# user_data.sh

until pg_isready -h epl-predictions-postgres.cxyk88y8u873.eu-south-1.rds.amazonaws.com -U postgres_admin; do
   echo "Database not ready, waiting 30 seconds..."
   sleep 30
done
