# External access to the KVM device — a proposal

> This document is a **proposal**, not the only acceptable method. The device is fully
> functional on the local network without any of the options below; external access is an
> optional layer *on top* of it. The department may use its own methods (an institutional
> VPN, port-forwarding on its own gateway, etc.) — the device architecture does not constrain
> them.

## How it works internally (context)

The device follows a **single-origin** principle: the web UI, the API, and the WebSocket
channels (control, front panel) are all served from one address via a local reverse proxy
(Caddy on `:80`). The browser uses **relative** paths, so the same application works at any
address it was opened from — local IP, `*.lan`, a VPN name, or a public domain — **without a
rebuild**.

It helps to distinguish two separate traffic planes:

1. **Control / signaling traffic** — HTTP(S) and WebSocket. Login, node listing, WebRTC
   signaling (offer/ICE), keyboard/mouse, front panel.
2. **Video** — WebRTC media, i.e. **UDP/SRTP**, sent *directly* between browser and device
   (port `30000/udp` on the device), not through the signaling channel.

Any external layer must serve **both** planes, otherwise the interface opens but the video
does not. This is exactly where some solutions fall short (see the Cloudflare section).

## Why external HTTPS matters

Plain HTTP is acceptable on the local network. But some browser features work **only in a
secure context (HTTPS)** — notably the Keyboard Lock API, which lets a fullscreen app capture
service keys (`Esc`, `Tab`, `Alt`, `Meta`) and pass them to the target PC (e.g. `Esc` to exit
the BIOS). Without HTTPS the browser intercepts those keys itself, and `Esc` merely leaves
fullscreen. So the external layer should provide **HTTPS** — both options below can.

---

## Option A — Tailscale (recommended; verified in practice)

Tailscale is a WireGuard-based network with its own coordination layer and relays. All
devices register into one account (tenant). For a donated device the tenant should belong to
the **department**, not a private individual.

Why it fits KVM well:

- Carries **both HTTP(S) and the UDP video natively** — it is a true L3 VPN, so WebRTC
  candidates on the Tailscale interface work directly, with no TURN and no port-forwarding.
- Traverses NAT on both ends by itself (DERP relays as fallback), so the department needs no
  public IP.
- Provides real HTTPS on a name like `https://<host>.<tailnet>.ts.net` with no manual
  certificate work.

Approximate steps on the device:

1. Install the client: `curl -fsSL https://tailscale.com/install.sh | sh`
2. Bring it up and authenticate into the department tenant: `sudo tailscale up`
3. Enable HTTPS certificates for the tenant in the Tailscale admin console (DNS → MagicDNS →
   HTTPS Certificates).
4. Publish the local web (Caddy on `:80`) over HTTPS:
   `sudo tailscale serve --bg http://localhost:80`
5. Open `https://<host>.<tailnet>.ts.net` from any department device running Tailscale.

Access is governed by ACLs in the tenant: only authorized users see the device. Limitation:
every connecting machine needs the Tailscale client — fine for department workstations; not
for "open any browser anywhere without installing anything".

---

## Option B — Cloudflare Tunnel (+ a separate path for video)

Cloudflare Tunnel (`cloudflared`) makes an outbound connection from the device to
Cloudflare's network and publishes the web on the department's domain
(`https://kvm.dept.example`) with no public IP and no router port-forwarding. Cloudflare
issues and renews the HTTPS certificate. For "open any browser anywhere, no VPN client" this
is more convenient than Tailscale.

Approximate steps: create a (free) Cloudflare account on the department's domain → install
`cloudflared` on the device → create a tunnel and route to the local Caddy
(`http://localhost:80`).

### Why a Cloudflare tunnel alone will **not** show video

Cloudflare Tunnel proxies **HTTP/HTTPS** (and, separately, L4 TCP for SSH/RDP). It carries all
control traffic — login, signaling, keyboard/mouse — and the interface opens fine. But **KVM
video is WebRTC media over UDP**, and UDP does not pass through Cloudflare's HTTP tunnel: to
receive the stream the browser needs a direct UDP connection to the device, which the tunnel
does not create. So through a "bare" tunnel you get a working interface and a **black video
player**. To make video work you need one of two extra steps: either (1) the department has a
real public IP and forwards UDP port `30000` to the device (media then flows directly, around
the tunnel), or (2) a **TURN server** is set up to relay the UDP media (self-hosted `coturn`
on a public node, or a managed TURN such as Cloudflare Realtime). Tailscale needs neither,
because it carries UDP itself.

---

## Short comparison

| | Tailscale (A) | Cloudflare Tunnel (B) |
|---|---|---|
| Control traffic (HTTP/WS) | yes | yes |
| Video (UDP) out of the box | **yes** | **no** — needs port-forward or TURN |
| Public IP at the department | not needed | not needed (tunnel) / needed (port-forward) |
| HTTPS | `tailscale serve` / `tailscale cert` | automatic from Cloudflare |
| Client on the user's machine | required | not required (plain browser) |
| Access owner | department's Tailscale tenant | Cloudflare account + department domain |

Bottom line: for access from a limited set of department machines, **Tailscale** is simpler
and more complete; for "any browser, anywhere", **Cloudflare**, but with a mandatory separate
solution for video (UDP forward or TURN).

---

## Sources

- Tailscale Serve — https://tailscale.com/kb/1312/serve, examples — https://tailscale.com/kb/1313/serve-examples/
- Tailscale, HTTPS certificates — https://tailscale.com/kb/1153/enabling-https
- Cloudflare Tunnel — https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/
- Cloudflare: WebRTC uses UDP and does not flow through HTTP proxies —
  https://developers.cloudflare.com/cloudflare-one/remote-browser-isolation/network-dependencies/
- coturn (self-hosted TURN server) — https://github.com/coturn/coturn
- Cloudflare Realtime (managed TURN) — https://developers.cloudflare.com/realtime/
