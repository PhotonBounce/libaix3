"""
knowledge_base.py — Curated Q&A knowledge for training the libaix classifier.

Organizes knowledge into *domains* (networking, internet, intranet, security, …).
Each entry is a (question/query, answer, domain_tag) triple.
New domains can be added by extending KNOWLEDGE or loading external JSON.
"""

from __future__ import annotations

import json
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────
# Knowledge entries: (question, answer, domain)
# ──────────────────────────────────────────────────────────────────────

KNOWLEDGE: list[tuple[str, str, str]] = [
    # ── NETWORKING (OSI, TCP/IP, protocols) ───────────────────────────
    ("What is the OSI model?",
     "The OSI (Open Systems Interconnection) model is a 7-layer framework that standardizes network communication: Physical, Data Link, Network, Transport, Session, Presentation, and Application.",
     "networking"),
    ("What are the 7 layers of the OSI model?",
     "Layer 1: Physical, Layer 2: Data Link, Layer 3: Network, Layer 4: Transport, Layer 5: Session, Layer 6: Presentation, Layer 7: Application.",
     "networking"),
    ("What is TCP?",
     "TCP (Transmission Control Protocol) is a connection-oriented transport layer protocol that provides reliable, ordered delivery of data between applications using a three-way handshake.",
     "networking"),
    ("What is UDP?",
     "UDP (User Datagram Protocol) is a connectionless transport layer protocol that sends datagrams without establishing a connection, offering low latency but no delivery guarantees.",
     "networking"),
    ("What is the difference between TCP and UDP?",
     "TCP is connection-oriented with guaranteed delivery and ordering; UDP is connectionless with no delivery guarantee but lower latency. TCP is used for web/email; UDP for streaming/gaming.",
     "networking"),
    ("What is an IP address?",
     "An IP address is a unique numerical label assigned to each device on a network. IPv4 uses 32-bit addresses (e.g. 192.168.1.1); IPv6 uses 128-bit addresses.",
     "networking"),
    ("What is a subnet mask?",
     "A subnet mask divides an IP address into network and host portions. For example, 255.255.255.0 (/24) means the first 24 bits identify the network and the last 8 bits identify hosts.",
     "networking"),
    ("What is DNS?",
     "DNS (Domain Name System) translates human-readable domain names (like google.com) into IP addresses that computers use to route traffic.",
     "networking"),
    ("What is DHCP?",
     "DHCP (Dynamic Host Configuration Protocol) automatically assigns IP addresses, subnet masks, gateways, and DNS servers to devices on a network.",
     "networking"),
    ("What is a MAC address?",
     "A MAC (Media Access Control) address is a unique 48-bit hardware identifier assigned to a network interface card (NIC), written as six hex pairs like AA:BB:CC:DD:EE:FF.",
     "networking"),
    ("What is a router?",
     "A router is a Layer 3 device that forwards packets between different networks by examining destination IP addresses and using routing tables.",
     "networking"),
    ("What is a switch?",
     "A network switch is a Layer 2 device that forwards frames within a LAN by learning MAC addresses and building a forwarding table.",
     "networking"),
    ("What is ARP?",
     "ARP (Address Resolution Protocol) maps IP addresses to MAC addresses on a local network, allowing Layer 2 frame delivery.",
     "networking"),
    ("What is a VLAN?",
     "A VLAN (Virtual LAN) logically segments a physical network at Layer 2, isolating broadcast domains without requiring separate hardware.",
     "networking"),
    ("What is NAT?",
     "NAT (Network Address Translation) maps private IP addresses to a public IP, allowing multiple devices to share one public address for internet access.",
     "networking"),
    ("What is a firewall?",
     "A firewall monitors and filters network traffic based on security rules, blocking unauthorized access while permitting legitimate communication.",
     "networking"),
    ("What is a gateway?",
     "A gateway is a node that serves as an access point between two networks, often the router that connects a LAN to the internet.",
     "networking"),
    ("What is ICMP?",
     "ICMP (Internet Control Message Protocol) is used for diagnostic and error reporting (e.g. ping and traceroute) at the network layer.",
     "networking"),
    ("What is a port number?",
     "A port number (0-65535) identifies a specific process or service on a host. Well-known ports: HTTP=80, HTTPS=443, SSH=22, DNS=53.",
     "networking"),
    ("What is bandwidth?",
     "Bandwidth is the maximum rate of data transfer across a network path, measured in bits per second (bps, Mbps, Gbps).",
     "networking"),
    ("What is latency?",
     "Latency is the time delay for data to travel from source to destination, measured in milliseconds. Lower latency means faster response.",
     "networking"),
    ("What is packet loss?",
     "Packet loss occurs when data packets fail to reach their destination, causing retransmissions (TCP) or gaps (UDP). Common causes: congestion, faulty hardware.",
     "networking"),

    # ── INTERNET ──────────────────────────────────────────────────────
    ("What is the internet?",
     "The internet is a global network of interconnected networks using the TCP/IP protocol suite, enabling communication and data exchange worldwide.",
     "internet"),
    ("What is HTTP?",
     "HTTP (HyperText Transfer Protocol) is an application-layer protocol for transferring web pages and resources between clients (browsers) and servers.",
     "internet"),
    ("What is HTTPS?",
     "HTTPS is HTTP over TLS/SSL, encrypting data in transit to protect confidentiality and integrity between browser and server.",
     "internet"),
    ("What is a URL?",
     "A URL (Uniform Resource Locator) is the address of a resource on the web, consisting of scheme (https), host (example.com), path (/page), and optional query/fragment.",
     "internet"),
    ("What is a web browser?",
     "A web browser is client software (Chrome, Firefox, Safari) that requests, renders, and displays web pages using HTTP/HTTPS.",
     "internet"),
    ("What is a web server?",
     "A web server is software (Apache, Nginx) that listens for HTTP requests and serves web pages, APIs, or files to clients.",
     "internet"),
    ("What is an API?",
     "An API (Application Programming Interface) defines how software components interact. Web APIs use HTTP to exchange data, often in JSON format.",
     "internet"),
    ("What is REST?",
     "REST (Representational State Transfer) is an architectural style for web APIs using standard HTTP methods (GET, POST, PUT, DELETE) on resources identified by URLs.",
     "internet"),
    ("What is a domain name?",
     "A domain name is a human-readable address (like github.com) that maps to an IP address via DNS, organized in a hierarchy (TLD, second-level, subdomain).",
     "internet"),
    ("What is cloud computing?",
     "Cloud computing delivers computing resources (servers, storage, databases) over the internet on-demand, with pay-as-you-go pricing. Major providers: AWS, Azure, GCP.",
     "internet"),
    ("What is a CDN?",
     "A CDN (Content Delivery Network) distributes content across geographically dispersed servers to reduce latency and improve load times for users worldwide.",
     "internet"),
    ("What is FTP?",
     "FTP (File Transfer Protocol) is used to transfer files between client and server over TCP, typically on port 21. SFTP adds SSH encryption.",
     "internet"),
    ("What is SSH?",
     "SSH (Secure Shell) is a protocol for secure remote login and command execution over an encrypted channel, typically on port 22.",
     "internet"),
    ("What is TLS?",
     "TLS (Transport Layer Security) is a cryptographic protocol that provides encryption, authentication, and integrity for data in transit. It replaced SSL.",
     "internet"),
    ("What is a cookie?",
     "An HTTP cookie is a small piece of data stored by the browser, sent with requests to maintain session state, preferences, or tracking information.",
     "internet"),
    ("What is WebSocket?",
     "WebSocket is a protocol providing full-duplex communication over a single TCP connection, enabling real-time data transfer between client and server.",
     "internet"),

    # ── INTRANET ──────────────────────────────────────────────────────
    ("What is an intranet?",
     "An intranet is a private network within an organization that uses internet technologies (TCP/IP, HTTP) for internal communication, collaboration, and resource sharing.",
     "intranet"),
    ("What is the difference between internet and intranet?",
     "The internet is a public global network; an intranet is a private organizational network. Intranets restrict access to authorized users and are typically behind firewalls.",
     "intranet"),
    ("What is an extranet?",
     "An extranet extends an intranet to authorized external users (partners, suppliers) via secure access, often using VPNs or authenticated portals.",
     "intranet"),
    ("What is a VPN?",
     "A VPN (Virtual Private Network) creates an encrypted tunnel over a public network, allowing remote users to securely access an intranet as if they were on the local network.",
     "intranet"),
    ("What is Active Directory?",
     "Active Directory (AD) is Microsoft's directory service for managing users, computers, and resources on a Windows network, providing authentication and authorization.",
     "intranet"),
    ("What is LDAP?",
     "LDAP (Lightweight Directory Access Protocol) is used to query and modify directory services like Active Directory, organizing entries in a hierarchical tree.",
     "intranet"),
    ("What is Single Sign-On?",
     "SSO (Single Sign-On) allows users to authenticate once and access multiple applications without re-entering credentials, using protocols like SAML or OAuth.",
     "intranet"),
    ("What is a proxy server?",
     "A proxy server acts as an intermediary between clients and the internet, providing caching, filtering, and anonymity. Reverse proxies sit in front of servers.",
     "intranet"),
    ("What is network segmentation?",
     "Network segmentation divides a network into isolated sub-networks (segments) to improve security, performance, and management using VLANs, subnets, or firewalls.",
     "intranet"),
    ("What is a DMZ in networking?",
     "A DMZ (Demilitarized Zone) is a perimeter network segment between the internal network and the internet, hosting public-facing services while protecting internal resources.",
     "intranet"),

    # ── SECURITY ──────────────────────────────────────────────────────
    ("What is encryption?",
     "Encryption converts plaintext into ciphertext using an algorithm and key, making data unreadable without the decryption key. Types: symmetric (AES) and asymmetric (RSA).",
     "security"),
    ("What is a DDoS attack?",
     "A DDoS (Distributed Denial of Service) attack overwhelms a target with traffic from many sources, making services unavailable to legitimate users.",
     "security"),
    ("What is phishing?",
     "Phishing is a social engineering attack that uses fake emails or websites to trick users into revealing credentials, financial info, or installing malware.",
     "security"),
    ("What is malware?",
     "Malware is malicious software designed to damage or exploit systems. Types include viruses, worms, trojans, ransomware, spyware, and adware.",
     "security"),
    ("What is a zero-day vulnerability?",
     "A zero-day vulnerability is a software flaw unknown to the vendor with no available patch, exploitable by attackers before a fix is released.",
     "security"),
    ("What is two-factor authentication?",
     "2FA requires two forms of identity verification: something you know (password) and something you have (phone/token) or are (biometrics), adding a security layer.",
     "security"),
    ("What is an SSL certificate?",
     "An SSL/TLS certificate authenticates a website's identity and enables encrypted connections. Issued by Certificate Authorities (CAs), it contains the public key.",
     "security"),
    ("What is a man-in-the-middle attack?",
     "A MITM attack intercepts communication between two parties, allowing the attacker to eavesdrop or alter data. HTTPS and certificate pinning help prevent this.",
     "security"),
    ("What is SQL injection?",
     "SQL injection is an attack where malicious SQL code is inserted into input fields to manipulate a database. Prevention: parameterized queries and input validation.",
     "security"),
    ("What is XSS?",
     "XSS (Cross-Site Scripting) injects malicious scripts into web pages viewed by others. Prevention: output encoding, Content Security Policy, input sanitization.",
     "security"),

    # ── PROTOCOLS & STANDARDS ─────────────────────────────────────────
    ("What is IPv4?",
     "IPv4 is the fourth version of the Internet Protocol using 32-bit addresses (4.3 billion possible). Addresses look like 192.168.0.1. Limited address space led to IPv6.",
     "networking"),
    ("What is IPv6?",
     "IPv6 uses 128-bit addresses (virtually unlimited), written in hex like 2001:0db8::1. It provides built-in IPsec, simplified headers, and no need for NAT.",
     "networking"),
    ("What is BGP?",
     "BGP (Border Gateway Protocol) is the routing protocol that manages how packets are routed across the internet between autonomous systems (AS).",
     "networking"),
    ("What is OSPF?",
     "OSPF (Open Shortest Path First) is a link-state interior gateway protocol that uses Dijkstra's algorithm to find the shortest path within an autonomous system.",
     "networking"),
    ("What is SMTP?",
     "SMTP (Simple Mail Transfer Protocol) is used to send emails between servers on port 25/587. It handles outgoing mail; POP3/IMAP handle retrieval.",
     "internet"),
    ("What is IMAP?",
     "IMAP (Internet Message Access Protocol) retrieves email from a server while keeping messages stored server-side, allowing multi-device access.",
     "internet"),

    # ── GENERAL / META ────────────────────────────────────────────────
    ("What is libaix?",
     "libaix is a neural network built from scratch using only NumPy. It supports multiple activations, optimizers, and can learn to classify text about networking topics.",
     "general"),
    ("Who made libaix?",
     "libaix was built as an open-source project to demonstrate neural networks from scratch without ML frameworks, hosted on GitHub.",
     "general"),
    ("What can this AI do?",
     "I can answer questions about networking, internet, intranet, and security topics. I was trained on a curated knowledge base using a neural network built with only NumPy.",
     "general"),
    ("Hello",
     "Hello! I'm libaix, a neural network that knows about networking, internet, intranet, and security. Ask me anything about these topics!",
     "general"),
    ("Help",
     "I can answer questions about: networking (TCP/IP, OSI, routing), internet (HTTP, DNS, APIs), intranet (VPN, AD, SSO), and security (encryption, attacks, 2FA). Just ask!",
     "general"),
]


def get_domains() -> list[str]:
    """Return sorted list of unique domain tags."""
    return sorted(set(domain for _, _, domain in KNOWLEDGE))


def get_questions() -> list[str]:
    return [q for q, _, _ in KNOWLEDGE]


def get_answers() -> list[str]:
    return [a for _, a, _ in KNOWLEDGE]


def get_domain_labels() -> list[str]:
    return [d for _, _, d in KNOWLEDGE]


def load_extra_knowledge(path: str | Path) -> list[tuple[str, str, str]]:
    """Load additional Q&A entries from a JSON file.

    Expected format: [{"question": "...", "answer": "...", "domain": "..."}]
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [(e["question"], e["answer"], e["domain"]) for e in data]
