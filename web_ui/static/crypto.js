/**
 * 前端加密工具 - 用于API密钥的安全传输
 * 使用AES-256-GCM加密，与后端兼容
 */

class CryptoUtils {
    // 固定盐值 - 必须与后端一致
    static SALT = 'MEMOS_TRANSPORT_SALT_2026_V1';

    // 默认传输密钥 - 必须与后端一致
    static DEFAULT_KEY = 'MemOS_Secure_Transport_Key_2026';

    /**
     * 从密码派生密钥
     */
    static async deriveKey(password) {
        const encoder = new TextEncoder();
        const passwordData = encoder.encode(password);
        const saltData = encoder.encode(this.SALT);

        // 导入密码
        const keyMaterial = await crypto.subtle.importKey(
            'raw',
            passwordData,
            { name: 'PBKDF2' },
            false,
            ['deriveBits']
        );

        // 派生256位密钥
        const keyBits = await crypto.subtle.deriveBits(
            {
                name: 'PBKDF2',
                salt: saltData,
                iterations: 100000,
                hash: 'SHA-256'
            },
            keyMaterial,
            256
        );

        // 导入为AES密钥
        return await crypto.subtle.importKey(
            'raw',
            keyBits,
            { name: 'AES-GCM' },
            false,
            ['encrypt', 'decrypt']
        );
    }

    /**
     * 加密数据
     */
    static async encrypt(plaintext, key = null) {
        try {
            const cryptoKey = key || await this.deriveKey(this.DEFAULT_KEY);
            const encoder = new TextEncoder();
            const data = encoder.encode(plaintext);

            // 生成随机nonce (12 bytes)
            const nonce = crypto.getRandomValues(new Uint8Array(12));

            // 加密
            const ciphertext = await crypto.subtle.encrypt(
                {
                    name: 'AES-GCM',
                    iv: nonce
                },
                cryptoKey,
                data
            );

            // 格式: version(1) + nonce(12) + ciphertext
            const version = new Uint8Array([1]);
            const encrypted = new Uint8Array(1 + 12 + ciphertext.byteLength);
            encrypted.set(version, 0);
            encrypted.set(nonce, 1);
            encrypted.set(new Uint8Array(ciphertext), 13);

            // Base64编码
            return btoa(String.fromCharCode(...encrypted));
        } catch (error) {
            console.error('加密失败:', error);
            throw error;
        }
    }

    /**
     * 解密数据
     */
    static async decrypt(encryptedBase64, key = null) {
        try {
            const cryptoKey = key || await this.deriveKey(this.DEFAULT_KEY);

            // Base64解码
            const encrypted = new Uint8Array(
                atob(encryptedBase64).split('').map(c => c.charCodeAt(0))
            );

            // 检查版本
            const version = encrypted[0];
            if (version !== 1) {
                throw new Error(`不支持的加密版本: ${version}`);
            }

            // 提取nonce和密文
            const nonce = encrypted.slice(1, 13);
            const ciphertext = encrypted.slice(13);

            // 解密
            const decrypted = await crypto.subtle.decrypt(
                {
                    name: 'AES-GCM',
                    iv: nonce
                },
                cryptoKey,
                ciphertext
            );

            const decoder = new TextDecoder();
            return decoder.decode(decrypted);
        } catch (error) {
            console.error('解密失败:', error);
            return null;
        }
    }
}

// 导出加密工具
window.CryptoUtils = CryptoUtils;
