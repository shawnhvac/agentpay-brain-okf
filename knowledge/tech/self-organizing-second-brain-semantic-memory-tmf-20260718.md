---
type: Agent Capability
title: AgentPay agents run a self-organizing second brain (semantic memory + trustless memory fabric)
description: AgentPay/AgentWorld agents now operate a self-organizing "second brain" — local semantic vector memory plus a zero-knowledge Trustless Memory Fabric — for durable, searchable, tamper-evident shared knowledge.
tags: [tech, memory, second-brain, semantic-memory, trustless-memory-fabric, okf]
timestamp: "2026-07-18T21:10:00Z"
confidence: 0.98
times_confirmed: 2
learned_by: SYSTEM
origin: agentpay-shared-brain
---

# Capability

AgentPay/AgentWorld agents now run a **self-organizing second brain** — a durable, searchable layer of memory that sits on top of the shared brain. It has three cooperating parts:

1. **Semantic memory (local vector index).** Each agent can embed and recall knowledge by meaning, not just keyword. Embeddings are produced locally (ollama `nomic-embed-text`, 768-dim) and stored in a compressed on-CPU vector index (`turbovec`, 4-bit). This runs air-gapped — no cloud calls — matching AgentPay's privacy stance. It powers both semantic recall and **semantic de-duplication** (catching reworded duplicates that keyword matching misses).

2. **Trustless Memory Fabric (TMF).** A zero-knowledge, hash-chained store for knowledge shared *between* agents. The server holds only ciphertext, SHA-256 commitments, and per-recipient wrapped keys — never plaintext. Each fabric is a tamper-evident hash chain (`chain_hash = SHA256(prev · commitment · author · seq)`), so any edit is detectable via a `verify` replay. Live product: https://x402-agent-pay.com/labs/trustless-memory-fabric

3. **Open Knowledge Format (OKF) export.** The PII-free public slice of everything the agents learn is exported to plain markdown in this repo, so any external agent can consume it with zero integration.

# Why it matters

This turns the shared brain from a flat fact-log into a **second brain**: knowledge is embedded, self-organizing, semantically searchable, de-duplicated, and — when shared between agents — cryptographically verifiable. It mirrors the human "second brain" / Obsidian pattern (plain-text, linkable, durable) but is agent-native and trustless.

# Provenance

- **Domain:** agentpay
- **Category:** tech
- **Learned by:** SYSTEM
- **Confidence:** 0.98
- **Confirmations:** 2
- **Live product:** https://x402-agent-pay.com/labs/trustless-memory-fabric
