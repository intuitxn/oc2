# Network configuration

`INTUITXN_NETWORK` is the canonical HTTP(S) relay base URL. `oc2-network.sh` falls back to `BUZZ_RELAY_URL`, then `https://intuitxn.communities.buzz.xyz`, exports the Buzz CLI alias, and derives `INTUITXN_NETWORK_WS`. Invalid schemes fail. `oc2-node.sh install` persists the canonical URL in launchd; `oc2-agent.sh` loads the same helper.

```sh
export INTUITXN_NETWORK=https://intuitxn.communities.buzz.xyz
. ~/opencode2/script/oc2-network.sh
buzz channels list
```

Identity is configured separately. This does not add anonymous channel access or change signing-key handling. The live host inherited a Buzz identity during verification; a clean process without an identity cannot list channels.

The versioned `script/plugins/buzz.ts` is the draft-only node plugin. Copy it to the work profile's `config/opencode/plugin/buzz.ts` before publishing a bundle; `oc2-team.sh pack` packages that profile and the network helper. It never sends drafts.

Run `sh script/oc2-network.test.sh` for default, legacy, precedence, WebSocket derivation and invalid-scheme checks.
