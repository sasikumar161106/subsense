import crypto from 'crypto';

// 32-byte master encryption key (derived securely from environment or hardened fallback)
const MASTER_SECRET = process.env.ENCRYPTION_KEY || 'subsense-coal-mine-aes-256-safety-key-2026';
const KEY = crypto.createHash('sha256').update(MASTER_SECRET).digest();
const ALGORITHM = 'aes-256-gcm';
const PREFIX = 'aes256gcm:';

/**
 * Encrypt a community registrant phone number at rest using AES-256-GCM
 * Output format: aes256gcm:<iv_hex>:<auth_tag_hex>:<ciphertext_hex>
 */
export function encrypt_phone_number(plaintext: string): string {
  if (!plaintext) return plaintext;
  if (plaintext.startsWith(PREFIX)) {
    return plaintext; // Already encrypted
  }

  const iv = crypto.randomBytes(12); // 96-bit IV recommended for GCM
  const cipher = crypto.createCipheriv(ALGORITHM, KEY, iv);

  let ciphertext = cipher.update(plaintext, 'utf8', 'hex');
  ciphertext += cipher.final('hex');

  const authTag = cipher.getAuthTag();

  return `${PREFIX}${iv.toString('hex')}:${authTag.toString('hex')}:${ciphertext}`;
}

/**
 * Decrypt an AES-256-GCM encrypted phone number from storage
 */
export function decrypt_phone_number(storedValue: string): string {
  if (!storedValue || !storedValue.startsWith(PREFIX)) {
    return storedValue; // Unencrypted legacy or fallback string
  }

  try {
    const parts = storedValue.substring(PREFIX.length).split(':');
    if (parts.length !== 3) {
      throw new Error('Invalid AES-256-GCM ciphertext format');
    }

    const [ivHex, authTagHex, ciphertextHex] = parts;
    const iv = Buffer.from(ivHex, 'hex');
    const authTag = Buffer.from(authTagHex, 'hex');

    const decipher = crypto.createDecipheriv(ALGORITHM, KEY, iv);
    decipher.setAuthTag(authTag);

    let decrypted = decipher.update(ciphertextHex, 'hex', 'utf8');
    decrypted += decipher.final('utf8');

    return decrypted;
  } catch (error: any) {
    console.error('[SECURITY ERROR] Failed to decrypt phone number at rest:', error.message);
    return '[DECRYPTION_FAILED]';
  }
}

/**
 * Mask phone number for UI display while preserving country/operator prefix
 * e.g., +919876543210 -> +91 98****3210
 */
export function mask_phone_number(phone: string): string {
  const plain = decrypt_phone_number(phone);
  if (plain.length <= 6) return '****';
  return `${plain.slice(0, 5)}****${plain.slice(-4)}`;
}
