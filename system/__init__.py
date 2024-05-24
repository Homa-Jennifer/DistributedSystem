import socket
import threading
import os
import psutil
import sys
import time
from random import randint
from prometheus_client import start_http_server, Gauge
from guizero import App


def kill_process_using_port(port):
    # Find process ID (PID) using the specified port
    os.system(f'lsof -ti:{port} | xargs kill -9')   

class Server:
    cpu_usage = Gauge('cpu_usage', 'CPU usage of the server')
    def __init__(self, host, port):
        # Initialize the server with host and port
        self.host = host
        self.port = port
        # Dictionary to store connected clients
        self.clients = {}
        # Create a TCP socket
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Bind the socket to the host and port
        self.server_socket.bind((self.host, self.port))
        # Listen for incoming connections
        self.server_socket.listen(5)
        print(f"Server started on {self.host}:{self.port}")

    def handle_client(self, client_socket, client_address, username):
        # Function to handle individual client connections
        while True:
            try:
                # Receive message from client
                message = client_socket.recv(1024).decode("utf-8")
                # Check if message is empty
                if not message:
                    # If empty, remove the client
                    self.remove_client(client_socket)
                    break
                print(f"Received message from {username}: {message}")
                # Check if message is private
                if message.startswith("@private"):
                    recipient_username, private_message = message.split(maxsplit=2)[1:]
                    # Check if recipient is connected
                    if recipient_username in self.clients:
                        recipient_socket = self.clients[recipient_username]
                        # Send private message to recipient
                        recipient_socket.send(f"(Private) {username}: {private_message}".encode("utf-8"))
                    else:
                        # Notify client that recipient is not found
                        client_socket.send("User not found".encode("utf-8"))
                # Check if message is for all clients
                elif message.startswith("@global"):
                    global_message = message.split(maxsplit=1)[1]
                    # Send message to all clients except sender
                    message_to_send = f"(Global) {username}: {global_message}"
                    for client in self.clients.values():
                        if client != client_socket:
                            client.send(message_to_send.encode("utf-8"))
                # Check if message is to list available clients
                elif message.startswith("@list"):
                    available_clients = "Available clients:\n"
                    for client_name in self.clients:
                        available_clients += f"- {client_name}\n"
                    client_socket.send(available_clients.encode("utf-8"))
                elif message.startswith("@exit"):
                    # Remove the client from the server
                    self.remove_client(client_socket)
                    # Close the client socket
                    client_socket.close()
                    break
                elif message.startswith("@restart"):
                    client_socket.send("Do you want to be a server (s) or remain a client (c)? ".encode("utf-8"))
                    restart_choice = client_socket.recv(1024).decode("utf-8").strip().lower()
                    if restart_choice == "s":
                        # Close the server socket
                        self.server_socket.close()
                        # Remove the client from the server
                        self.remove_client(client_socket)
                        # Close the client socket
                        client_socket.close()
                        return "client"
                    elif restart_choice == "c":
                        client_socket.send("You are already a server".encode("utf-8"))
                else:
                    # Broadcast message to all clients
                    message_to_send = f"{username}: {message}"
                    for client in self.clients.values():
                        if client != client_socket:
                            client.send(message_to_send.encode("utf-8"))
            except Exception as e:
                print(e)
                # If any exception occurs, remove the client
                self.remove_client(client_socket)
                break

    def remove_client(self, client_socket):
        # Remove a client from the server
        for username, client in self.clients.items():
            if client == client_socket:
                print(f"{username} has left the chat")
                # Delete the client from the dictionary
                del self.clients[username]
                # Notify other clients about the client leaving
                for c in self.clients.values():
                    c.send(f"{username} has left the chat".encode("utf-8"))
                break

    def start(self):
        # Function to start the server
        while True:
            # Accept incoming connection
            client_socket, client_address = self.server_socket.accept()
            print("Client connected from", client_address)
            # Receive username from client
            username = client_socket.recv(1024).decode("utf-8")
            print(f"{username} has joined the chat")
            # Add client to the dictionary
            self.clients[username] = client_socket
            # Notify other clients about the new client
            for client in self.clients.values():
                if client != client_socket:
                    client.send(f"{username} has joined the chat".encode("utf-8"))
            # Handle client in a separate thread
            client_handler = threading.Thread(target=self.handle_client, args=(client_socket, client_address, username))
            client_handler.start()
            return "server"
            
class Client:
    def __init__(self, username, host, port):
        # Initialize the client with username, host, and port
        self.username = username
        self.host = host
        self.port = port
        # Create a TCP socket
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Connect to the server
        self.client_socket.connect((self.host, self.port))
        # Send username to the server
        self.client_socket.send(self.username.encode("utf-8"))
        print("Connected to server")

    def send_message(self, message):
        # Send message to the server
        self.client_socket.send(message.encode("utf-8"))

    def start_receiving(self): 
        # Function to start receiving messages from the server
        while True:
            try:
                # Receive message from the server
                message = self.client_socket.recv(1024).decode("utf-8")
                print(message)
            except Exception as e:
                print(e)
                break

def main():
    while True:
        # Main function to start server or client
        role = input("Do you want to be a server (s) or a client (c)? ").strip().lower()
        if role == "s":
            port = input("Enter the port number to run the server: ").strip()
            try:
                port = int(port)
                # If user selects server
                host = "localhost"
                server = Server(host, port)
                while True:
                    # Start the server
                    action = server.start()
                    if action == "client":
                        # If server wants to become a client
                        client = Client("Server", host, port)
                        # Start receiving messages in a separate thread
                        client_thread = threading.Thread(target=client.start_receiving)
                        client_thread.start()
                        break
                break
            except ValueError:
                print("Invalid port number. Please enter a valid integer.")
        elif role == "c":
            username = input("Enter your username: ").strip()
            host = input("Enter the server IP address (localhost): ").strip() or "localhost"
            port = input("Enter the server port number: ").strip()
            try:
                port = int(port)
                client = Client(username, host, port)
                # Start receiving messages from the server in a separate thread
                client_thread = threading.Thread(target=client.start_receiving)
                client_thread.start()
                # Provide instructions to the user
                print("\nInstructions:\n"
                      "- To chat with a client privately, use @private recipient_username message\n"
                      "- To chat with all clients globally, use @global message\n"
                      "- To see the available clients, use @list\n"
                      "- To exit the chat room, use @exit\n"
                      "- To restart the client/server, use @restart\n")
                while True:
                    # Allow the user to send messages
                    message = input("Enter your message: ")
                    if message == "@restart":
                        client.send_message(message)
                        restart_choice = input("Do you want to be a server (s) or remain a client (c)? ").strip().lower()
                        if restart_choice == "s":
                            break
                        elif restart_choice == "c":
                            continue
                    client.send_message(message)
            except ValueError:
                print("Invalid port number. Please enter a valid integer.")

if __name__ == "__main__":
    main()