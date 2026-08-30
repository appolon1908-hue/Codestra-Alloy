# Codestra Alloy Runtime Features

## Corporate collection features

- one deployment-controlled Codestra business per Alloy instance;
- one canonical environment, region, server and immutable deployment identity;
- business-scoped service file collection;
- explicitly mounted container JSON logs without Docker-socket access;
- persistent journald collection for platform or dedicated-host profiles only;
- controlled application/service labels derived from approved directory names;
- removal of filename and container identity from Loki stream labels;
- JSON-formatted Alloy self logs;
- private Alloy readiness and self-metrics endpoint;
- TLS-verified Loki write with deployment-controlled tenant ID;
- durable Loki WAL and bounded retry/backoff;
- defense-in-depth secret, personal-data, payload and SQL redaction;
- read-only root filesystem, non-root user, dropped Linux capabilities and no-new-privileges;
- private business-log and observability networks;
- immutable builder, upstream and final image inputs;
- source-native Alloy format and validation gates;
- explicit activation, ACL, tenant-isolation, redaction, WAL and recovery gates.

## Portfolio representation

The same runtime contract supports shared platform services and every managed business:

- Codestra
- MoneyBee
- Beyvra Trading
- Breero
- LARIM-A
- Transportation and Freight
- Booked4Seasons
- Codestra Social
- Klyrow Email
- Telnexa Messaging
- Kyqra
- Restaurant Platform
- Codestra Provisioning

## Deliberate non-features

Alloy does not:

- mount the Docker socket;
- mount the global Docker container directory;
- run privileged or on the host network;
- collect host metrics already owned by Node Exporter;
- collect container metrics already owned by cAdvisor;
- replace the OpenTelemetry Collector for application OTLP;
- create customer-, account-, user- or request-level Loki stream labels;
- retain raw credentials, customer payloads, broker/exchange signing material or financial records;
- expose a public native endpoint;
- mutate a business application or provider;
- send email, SMS or voice;
- execute n8n or write to Odoo;
- place, modify, cancel or approve a trade.
