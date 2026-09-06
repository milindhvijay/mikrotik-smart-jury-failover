# Additional WAN probe candidates

Initial candidate survey. A subset was subsequently deployed after a longer soak; see [completion notes](../completion.md) and the per-ISP selection JSON files. Eligible CSVs below are historical screening results, not the active configuration.

These are candidate inventories, not deployed configuration. Each address received 80 ICMP probes per ISP in four batches, with 1 second spacing and a 1 second timeout. The production timeout is 500 ms. Tests use the dedicated ISP monitor hosts and do not change router routes.

A preliminary pass requires zero observed loss, p95 below 150 ms, and p95 no greater than max(30 ms, 1.5 × median). This is a short reachability/jitter screen, not evidence of long-term availability. CSV baselines round the observed median up to the next 5 ms (minimum 10 ms); measure across busy and quiet periods before adoption.

Do not add every address as an independent vote. DNS aliases and multiple roots operated by Verisign are correlated; Caasify is a reseller listing, not necessarily a separate underlying network. Prefer one target per operator per family, preserving regional and ISP coverage. Confirm underlying origin ASNs before final balancing. More IPs increase probe traffic even when process count stays unchanged.

## BSNL

63 new addresses tested; 41 passed the preliminary screen ({6: 17, 4: 24}, family 4/6). Window: 2026-09-06T08:25:42.359751+00:00 to 2026-09-06T08:27:34.726743+00:00.

## KV

63 new addresses tested; 34 passed the preliminary screen ({6: 15, 4: 19}, family 4/6). Window: 2026-09-06T08:25:42.359467+00:00 to 2026-09-06T08:27:34.726722+00:00.

## Full comparison

RTTs are median / p95 in milliseconds. PASS means preliminary screen passed; HOLD needs further investigation; NO REPLY means no ICMP responses during this survey.

| Candidate | IP | BSNL: RTT; loss; result | KV: RTT; loss; result |
|---|---|---|---|
| [Cloudflare](https://developers.cloudflare.com/1.1.1.1/ip-addresses/) | `1.0.0.1` | 21.4 / 22.2; 0.0%; PASS | 11.6 / 12.2; 0.0%; PASS |
| [Caasify-Delhi-10](https://caasify.com/cloud-vps/looking-glass) | `103.189.51.11` | -; 100%; NO REPLY | -; 100%; NO REPLY |
| [Caasify-Delhi-6](https://caasify.com/cloud-vps/looking-glass) | `139.84.132.104` | -; 100%; NO REPLY | -; 100%; NO REPLY |
| [Caasify-Bangalore-5](https://caasify.com/cloud-vps/looking-glass) | `139.84.138.108` | 13.7 / 14.1; 0.0%; PASS | 32.5 / 32.9; 0.0%; PASS |
| [Quad9](https://docs.quad9.net/services/) | `149.112.112.112` | 37.4 / 60.0; 0.0%; HOLD | 30.8 / 47.4; 0.0%; HOLD |
| [Caasify-Singapore-1](https://caasify.com/cloud-vps/looking-glass) | `159.65.132.3` | 54.0 / 54.7; 0.0%; PASS | 63.5 / 64.6; 0.0%; PASS |
| [Root-B-USC](https://www.iana.org/domains/root/servers) | `170.247.170.2` | 52.5 / 53.0; 0.0%; PASS | 247.0 / 247.0; 0.0%; HOLD |
| [Caasify-Chennai-5](https://caasify.com/cloud-vps/looking-glass) | `172.232.96.36` | 19.9 / 20.3; 0.0%; PASS | 16.3 / 17.1; 0.0%; PASS |
| [Akamai-Singapore-2](https://sg-sin-2.speedtest.linode.com/) | `172.236.129.31` | 49.8 / 50.3; 0.0%; PASS | 72.5 / 74.1; 0.0%; PASS |
| [DNS.SB-xTom](https://dns.sb/guide/) | `185.222.222.222` | 50.1 / 50.7; 0.0%; PASS | 152.0 / 153.0; 0.0%; HOLD |
| [CleanBrowsing](https://cleanbrowsing.org/support/troubleshooting/command-line-dns) | `185.228.168.9` | 49.5 / 50.0; 0.0%; PASS | 270.0 / 271.0; 0.0%; HOLD |
| [CleanBrowsing](https://cleanbrowsing.org/support/troubleshooting/command-line-dns) | `185.228.169.9` | 163.0 / 165.0; 0.0%; HOLD | 264.0 / 265.0; 0.0%; HOLD |
| [Tier4-Mumbai-DC2](https://lg-bom2.advancedserverdns.com/) | `188.208.141.1` | 39.0 / 62.7; 0.0%; HOLD | -; 100%; NO REPLY |
| [Root-G-DoD](https://www.iana.org/domains/root/servers) | `192.112.36.4` | -; 100%; NO REPLY | -; 100%; NO REPLY |
| [Root-E-NASA](https://www.iana.org/domains/root/servers) | `192.203.230.10` | 31.8 / 32.5; 0.0%; PASS | 23.3 / 24.1; 0.0%; PASS |
| [Root-C-Cogent](https://www.iana.org/domains/root/servers) | `192.33.4.12` | 69.0 / 69.5; 0.0%; PASS | 65.5 / 65.9; 0.0%; PASS |
| [Root-I-Netnod](https://www.iana.org/domains/root/servers) | `192.36.148.17` | 52.1 / 52.8; 0.0%; PASS | 65.5 / 66.1; 0.0%; PASS |
| [Root-J-Verisign](https://www.iana.org/domains/root/servers) | `192.58.128.30` | 15.4 / 24.8; 0.0%; PASS | 27.3 / 27.9; 0.0%; PASS |
| [Root-A-Verisign](https://www.iana.org/domains/root/servers) | `198.41.0.4` | 51.3 / 52.0; 0.0%; PASS | 175.0 / 176.0; 0.0%; HOLD |
| [Root-H-Army](https://www.iana.org/domains/root/servers) | `198.97.190.53` | 155.0 / 158.0; 0.0%; HOLD | 61.1 / 61.8; 0.0%; PASS |
| [Root-D-UMD](https://www.iana.org/domains/root/servers) | `199.7.91.13` | 38.9 / 55.3; 0.0%; PASS | 31.9 / 42.6; 0.0%; PASS |
| [Caasify-Singapore-6](https://caasify.com/cloud-vps/looking-glass) | `2001:19f0:4400:4001:5400:ff:fe32:b7e5` | 55.7 / 56.5; 2.5%; HOLD | 62.4 / 63.2; 3.7%; HOLD |
| [Hurricane-Electric](https://forums.he.net/index.php?topic=3996.0) | `2001:470:20::2` | 405.0 / 410.0; 13.7%; HOLD | 236.0 / 242.0; 1.2%; HOLD |
| [Google](https://developers.google.com/speed/public-dns/docs/using) | `2001:4860:4860::8844` | 18.8 / 20.7; 0.0%; PASS | 13.4 / 14.0; 0.0%; PASS |
| [Root-G-DoD](https://www.iana.org/domains/root/servers) | `2001:500:12::d0d` | -; 100%; NO REPLY | -; 100%; NO REPLY |
| [Root-H-Army](https://www.iana.org/domains/root/servers) | `2001:500:1::53` | 144.0 / 144.0; 1.2%; HOLD | 178.0 / 179.0; 0.0%; HOLD |
| [Root-C-Cogent](https://www.iana.org/domains/root/servers) | `2001:500:2::c` | 73.8 / 75.5; 0.0%; PASS | 237.0 / 238.0; 0.0%; HOLD |
| [Root-D-UMD](https://www.iana.org/domains/root/servers) | `2001:500:2d::d` | 40.8 / 65.3; 0.0%; HOLD | 19.5 / 20.0; 0.0%; PASS |
| [Root-E-NASA](https://www.iana.org/domains/root/servers) | `2001:500:a8::e` | 25.4 / 25.8; 0.0%; PASS | 19.4 / 19.9; 0.0%; PASS |
| [Root-A-Verisign](https://www.iana.org/domains/root/servers) | `2001:503:ba3e::2:30` | 53.2 / 53.9; 0.0%; PASS | 310.0 / 311.0; 0.0%; HOLD |
| [Root-J-Verisign](https://www.iana.org/domains/root/servers) | `2001:503:c27::2:30` | 52.7 / 53.5; 0.0%; PASS | 27.2 / 27.8; 0.0%; PASS |
| [Root-I-Netnod](https://www.iana.org/domains/root/servers) | `2001:7fe::53` | 52.5 / 53.3; 0.0%; PASS | 78.6 / 79.4; 0.0%; PASS |
| [Root-M-WIDE](https://www.iana.org/domains/root/servers) | `2001:dc3::35` | 52.7 / 53.8; 1.2%; HOLD | 161.0 / 161.0; 0.0%; HOLD |
| [Root-M-WIDE](https://www.iana.org/domains/root/servers) | `202.12.27.33` | 34.0 / 35.0; 0.0%; PASS | 30.7 / 31.3; 0.0%; PASS |
| [E2E-Noida](https://lg.e2enetworks.net/) | `205.147.103.169` | 51.8 / 53.2; 0.0%; PASS | 49.5 / 50.0; 0.0%; PASS |
| [Caasify-Mumbai-6](https://caasify.com/cloud-vps/looking-glass) | `2401:c080:2600:1066:5400:3ff:fe19:3934` | -; 100%; NO REPLY | -; 100%; NO REPLY |
| [Caasify-Bangalore-5](https://caasify.com/cloud-vps/looking-glass) | `2401:c080:3080:2846:5400:4ff:fec6:7915` | -; 100%; NO REPLY | -; 100%; NO REPLY |
| [Caasify-Delhi-6](https://caasify.com/cloud-vps/looking-glass) | `2401:c080:3400:290e:5400:4ff:fe9a:29a` | -; 100%; NO REPLY | -; 100%; NO REPLY |
| [Akamai-Singapore-2](https://sg-sin-2.speedtest.linode.com/) | `2600:3c15::f03c:94ff:fe13:db17` | 51.4 / 51.9; 0.0%; PASS | 66.3 / 66.9; 0.0%; PASS |
| [ControlD](https://docs.controld.com/docs/free-dns) | `2606:1a40:1::` | 42.5 / 43.3; 0.0%; PASS | 30.0 / 30.7; 0.0%; PASS |
| [ControlD](https://docs.controld.com/docs/free-dns) | `2606:1a40::` | 43.8 / 45.1; 0.0%; PASS | 29.9 / 30.6; 0.0%; PASS |
| [Cloudflare](https://developers.cloudflare.com/1.1.1.1/ip-addresses/) | `2606:4700:4700::1001` | 25.6 / 26.3; 0.0%; PASS | 7.8 / 8.5; 0.0%; PASS |
| [Quad9](https://docs.quad9.net/services/) | `2620:fe::9` | 42.0 / 56.9; 0.0%; PASS | 17.1 / 17.9; 0.0%; PASS |
| [Quad9](https://docs.quad9.net/services/) | `2620:fe::fe` | 42.1 / 85.8; 0.0%; HOLD | 12.6 / 13.5; 0.0%; PASS |
| [Root-B-USC](https://www.iana.org/domains/root/servers) | `2801:1b8:10::b` | 54.3 / 55.3; 0.0%; PASS | 73.0 / 73.6; 0.0%; PASS |
| [Hetzner-Singapore](https://sin-speed.hetzner.com/) | `2a01:4ff:2ef::fa57:1` | -; 100%; NO REPLY | -; 100%; NO REPLY |
| [DNS.SB-xTom](https://dns.sb/guide/) | `2a09::` | 52.9 / 55.8; 0.0%; PASS | 181.0 / 181.0; 0.0%; HOLD |
| [CleanBrowsing](https://cleanbrowsing.org/support/troubleshooting/command-line-dns) | `2a0d:2a00:1::2` | 51.7 / 54.5; 0.0%; PASS | 76.1 / 76.6; 0.0%; PASS |
| [CleanBrowsing](https://cleanbrowsing.org/support/troubleshooting/command-line-dns) | `2a0d:2a00:2::2` | 53.4 / 62.0; 0.0%; PASS | 60.7 / 68.5; 0.0%; PASS |
| [AdGuard](https://adguard-dns.io/en/public-dns.html) | `2a10:50c0::ad1:ff` | 52.3 / 52.8; 0.0%; PASS | 60.2 / 64.7; 2.5%; HOLD |
| [AdGuard](https://adguard-dns.io/en/public-dns.html) | `2a10:50c0::ad2:ff` | 52.8 / 53.8; 3.7%; HOLD | 60.2 / 61.1; 0.0%; PASS |
| [DNS.SB-xTom](https://dns.sb/guide/) | `2a11::` | 53.0 / 53.7; 0.0%; PASS | 158.0 / 159.0; 0.0%; HOLD |
| [DNS.SB-xTom](https://dns.sb/guide/) | `45.11.45.11` | 49.1 / 49.7; 0.0%; PASS | 152.0 / 153.0; 0.0%; HOLD |
| [Caasify-Singapore-6](https://caasify.com/cloud-vps/looking-glass) | `45.32.100.168` | 49.1 / 49.6; 0.0%; PASS | 282.0 / 283.0; 0.0%; HOLD |
| [Hetzner-Singapore](https://sin-speed.hetzner.com/) | `5.223.7.195` | 49.3 / 50.1; 0.0%; PASS | 61.4 / 62.2; 0.0%; PASS |
| [Hurricane-Electric](https://forums.he.net/index.php?topic=3996.0) | `74.82.42.42` | 229.0 / 238.0; 1.2%; HOLD | 241.0 / 306.0; 0.0%; HOLD |
| [ControlD](https://docs.controld.com/docs/free-dns) | `76.76.10.0` | 26.4 / 27.4; 0.0%; PASS | 27.8 / 28.6; 0.0%; PASS |
| [ControlD](https://docs.controld.com/docs/free-dns) | `76.76.2.0` | 26.5 / 27.4; 0.0%; PASS | 27.8 / 28.7; 0.0%; PASS |
| [Google](https://developers.google.com/speed/public-dns/docs/using) | `8.8.4.4` | 18.0 / 18.4; 0.0%; PASS | 16.7 / 17.4; 0.0%; PASS |
| [Caasify-Mumbai-6](https://caasify.com/cloud-vps/looking-glass) | `85.28.66.100` | 171.0 / 179.0; 0.0%; HOLD | 291.0 / 296.0; 0.0%; HOLD |
| [Quad9](https://docs.quad9.net/services/) | `9.9.9.9` | 38.9 / 61.7; 0.0%; HOLD | 34.4 / 52.7; 0.0%; HOLD |
| [AdGuard](https://adguard-dns.io/en/public-dns.html) | `94.140.14.14` | 51.7 / 52.4; 0.0%; PASS | 59.6 / 60.3; 0.0%; PASS |
| [AdGuard](https://adguard-dns.io/en/public-dns.html) | `94.140.15.15` | 50.3 / 50.8; 0.0%; PASS | 80.8 / 81.3; 0.0%; PASS |
