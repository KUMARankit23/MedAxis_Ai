"""Generate a self-signed TLS certificate for MedAxis (localhost/dev use)."""
import datetime
import ipaddress
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import os

os.makedirs("nginx/certs", exist_ok=True)

# Generate 2048-bit RSA private key
key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

subject = issuer = x509.Name([
    x509.NameAttribute(NameOID.COUNTRY_NAME, "IN"),
    x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "State"),
    x509.NameAttribute(NameOID.LOCALITY_NAME, "City"),
    x509.NameAttribute(NameOID.ORGANIZATION_NAME, "MedAxis"),
    x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
])

now = datetime.datetime.now(datetime.timezone.utc)
cert = (
    x509.CertificateBuilder()
    .subject_name(subject)
    .issuer_name(issuer)
    .public_key(key.public_key())
    .serial_number(x509.random_serial_number())
    .not_valid_before(now)
    .not_valid_after(now + datetime.timedelta(days=365))
    .add_extension(
        x509.SubjectAlternativeName([
            x509.DNSName("localhost"),
            x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
        ]),
        critical=False,
    )
    .sign(key, hashes.SHA256())
)

# Write private key
with open("nginx/certs/privkey.pem", "wb") as f:
    f.write(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ))

# Write certificate
with open("nginx/certs/fullchain.pem", "wb") as f:
    f.write(cert.public_bytes(serialization.Encoding.PEM))

expiry = cert.not_valid_after_utc.strftime("%Y-%m-%d")
print("Self-signed TLS certificate generated successfully:")
print("  nginx/certs/privkey.pem")
print("  nginx/certs/fullchain.pem")
print("  Valid until: " + expiry)
print("")
print("For production, replace with real certs from Let's Encrypt:")
print("  certbot certonly --standalone -d yourdomain.com")
