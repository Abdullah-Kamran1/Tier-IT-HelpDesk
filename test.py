"""Auth0 Management API tools for identity & access operations using the official SDK."""
import os
from dotenv import load_dotenv
from auth0.management import ManagementClient
from auth0.authentication import Database 
import inspect

load_dotenv()

# Load environment configuration variables
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
AUTH0_CLIENT_ID = os.getenv("AUTH0_CLIENT_ID")
AUTH0_CLIENT_SECRET = os.getenv("AUTH0_CLIENT_SECRET")
AUTH0_CONNECTION = os.getenv("AUTH0_CONNECTION", "Username-Password-Authentication")


client = ManagementClient(
    domain=AUTH0_DOMAIN,
    client_id=AUTH0_CLIENT_ID,
    client_secret=AUTH0_CLIENT_SECRET
)

db_client = Database(domain=AUTH0_DOMAIN, client_id=AUTH0_CLIENT_ID)
# 1. Print all valid endpoints attached to a user
# print(dir(client.users))

print(dir(db_client))

# 2. Print all valid methods for modifying user MFA factors
# print(dir(client.users.authentication_methods))

# print(dir(client.users.roles))

# print("LIST:")
# print(inspect.signature(client.users.roles.list))

# print("ASSIGN:")
# print(inspect.signature(client.users.roles.assign))

# print("DELETE:")
# print(inspect.signature(client.users.roles.delete))


# print(dir(client.tickets))
# print(inspect.signature(client.tickets.change_password))

