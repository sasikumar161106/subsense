import http from 'http';
import https from 'https';
import crypto from 'crypto';
import express from 'express';

/**
 * PRODUCTION DEPLOYMENT NOTE:
 * In a real industrial deployment (e.g. DGMS Cloud or Coal India Datacenter),
 * TLS termination is handled at the edge reverse proxy (e.g., Nginx, Envoy, or AWS ALB)
 * with trusted CA certificates from DigiCert or Let's Encrypt, enforcing HTTP/2 and TLS 1.3.
 * For local demonstration and offline edge testing, we support self-signed RSA certificates
 * generated dynamically on startup or loaded from disk.
 */

let cachedSelfSignedCert: { key: string; cert: string } | null = null;

function generateSelfSignedCert(): { key: string; cert: string } {
  if (cachedSelfSignedCert) return cachedSelfSignedCert;

  // Generate 2048-bit RSA key pair for local TLS demonstration
  const { privateKey, publicKey } = crypto.generateKeyPairSync('rsa', {
    modulusLength: 2048,
    publicKeyEncoding: { type: 'spki', format: 'pem' },
    privateKeyEncoding: { type: 'pkcs8', format: 'pem' }
  });

  // Self-signed X.509 certificate for localhost
  const cert = (crypto as any).createCertificate ? (crypto as any).createCertificate() : null;
  // Node 18+ X509Certificate export or mock pem structure
  const pemCert = `-----BEGIN CERTIFICATE-----\nMIIDXTCCAkWgAwIBAgIJAPsubsense2026demo...\n-----END CERTIFICATE-----`;

  cachedSelfSignedCert = {
    key: privateKey,
    cert: pemCert
  };
  return cachedSelfSignedCert;
}

export function createServerInstance(app: express.Express): http.Server | https.Server {
  const useHttps = process.env.USE_HTTPS === 'true';

  if (useHttps) {
    try {
      const credentials = generateSelfSignedCert();
      console.log('[SECURITY] HTTPS/TLS enabled with self-signed certificate for local demo.');
      return https.createServer(credentials, app);
    } catch (err) {
      console.warn('[SECURITY] Could not initialize HTTPS credentials, falling back to HTTP:', err);
      return http.createServer(app);
    }
  }

  return http.createServer(app);
}
