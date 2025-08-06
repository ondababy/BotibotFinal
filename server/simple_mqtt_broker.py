#!/usr/bin/env python3
"""
Simple MQTT Broker for Windows
A lightweight MQTT broker using Python for testing purposes
"""
import socket
import threading
import time
import json
from datetime import datetime

class SimpleMQTTBroker:
    def __init__(self, host='0.0.0.0', port=1883):
        self.host = host
        self.port = port
        self.clients = {}
        self.subscriptions = {}
        self.running = False
        
    def start(self):
        """Start the MQTT broker"""
        self.running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            print(f"Simple MQTT Broker started on {self.host}:{self.port}")
            print("Waiting for connections...")
            
            while self.running:
                try:
                    client_socket, address = self.server_socket.accept()
                    print(f"New connection from {address}")
                    
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, address)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                    
                except Exception as e:
                    if self.running:
                        print(f"Error accepting connection: {e}")
                        
        except Exception as e:
            print(f"Error starting broker: {e}")
        finally:
            self.server_socket.close()
    
    def handle_client(self, client_socket, address):
        """Handle individual client connections"""
        client_id = f"{address[0]}:{address[1]}"
        self.clients[client_id] = {
            'socket': client_socket,
            'address': address,
            'subscriptions': set()
        }
        
        try:
            while self.running:
                data = client_socket.recv(1024)
                if not data:
                    break
                    
                # Simple message handling (not full MQTT protocol)
                try:
                    message = data.decode('utf-8')
                    if message.startswith('SUBSCRIBE:'):
                        topic = message.split(':', 1)[1].strip()
                        self.subscribe_client(client_id, topic)
                    elif message.startswith('PUBLISH:'):
                        parts = message.split(':', 2)
                        if len(parts) >= 3:
                            topic = parts[1].strip()
                            payload = parts[2].strip()
                            self.publish_message(topic, payload, client_id)
                except:
                    pass
                    
        except Exception as e:
            print(f"Error handling client {address}: {e}")
        finally:
            self.disconnect_client(client_id)
    
    def subscribe_client(self, client_id, topic):
        """Subscribe a client to a topic"""
        if client_id in self.clients:
            self.clients[client_id]['subscriptions'].add(topic)
            if topic not in self.subscriptions:
                self.subscriptions[topic] = set()
            self.subscriptions[topic].add(client_id)
            print(f"Client {client_id} subscribed to {topic}")
    
    def publish_message(self, topic, payload, sender_id):
        """Publish a message to all subscribers of a topic"""
        print(f"Publishing to {topic}: {payload[:50]}..." if len(payload) > 50 else f"Publishing to {topic}: {payload}")
        
        if topic in self.subscriptions:
            for client_id in self.subscriptions[topic].copy():
                if client_id != sender_id and client_id in self.clients:
                    try:
                        message = f"MESSAGE:{topic}:{payload}\n"
                        self.clients[client_id]['socket'].send(message.encode('utf-8'))
                    except:
                        self.disconnect_client(client_id)
    
    def disconnect_client(self, client_id):
        """Disconnect a client and clean up"""
        if client_id in self.clients:
            print(f"Client {client_id} disconnected")
            
            # Remove from subscriptions
            for topic in self.clients[client_id]['subscriptions']:
                if topic in self.subscriptions:
                    self.subscriptions[topic].discard(client_id)
                    if not self.subscriptions[topic]:
                        del self.subscriptions[topic]
            
            # Close socket
            try:
                self.clients[client_id]['socket'].close()
            except:
                pass
            
            del self.clients[client_id]
    
    def stop(self):
        """Stop the broker"""
        self.running = False
        for client_id in list(self.clients.keys()):
            self.disconnect_client(client_id)
        self.server_socket.close()

if __name__ == "__main__":
    print("Simple MQTT Broker for Windows")
    print("==============================")
    print("This is a basic MQTT broker for testing purposes.")
    print("For production, use Mosquitto or another full MQTT broker.")
    print()
    
    # For your network setup
    broker = SimpleMQTTBroker(host='0.0.0.0', port=1883)
    
    try:
        broker.start()
    except KeyboardInterrupt:
        print("\nStopping broker...")
        broker.stop()
    except Exception as e:
        print(f"Error: {e}")
