"""
加密工具模块 - 用于前后端安全传输
使用AES-256-GCM加密
"""

import base64
import os
import hashlib
from typing import Optional


class CryptoUtils:
    """加密工具类"""

    # 固定盐值 - 用于派生密钥
    SALT = b'MEMOS_TRANSPORT_SALT_2026_V1'

    @staticmethod
    def derive_key(password: str) -> bytes:
        """从密码派生32字节密钥"""
        return hashlib.pbkdf2_hmac('sha256', password.encode(), CryptoUtils.SALT, 100000, 32)

    @staticmethod
    def encrypt(plaintext: str, key: bytes) -> str:
        """
        使用AES-256-GCM加密

        Args:
            plaintext: 明文
            key: 32字节密钥

        Returns:
            base64编码的密文格式: version(1) + nonce(12) + tag(16) + ciphertext
        """
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM

            nonce = os.urandom(12)  # 96-bit nonce
            aesgcm = AESGCM(key)
            ciphertext = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)

            # 格式: version(1 byte) + nonce(12 bytes) + ciphertext(with tag)
            # version = 1 表示使用AES-256-GCM
            version = bytes([1])
            encrypted = version + nonce + ciphertext
            return base64.b64encode(encrypted).decode('utf-8')
        except ImportError:
            raise ImportError("请安装cryptography库: pip install cryptography")

    @staticmethod
    def decrypt(encrypted: str, key: bytes) -> Optional[str]:
        """
        使用AES-256-GCM解密

        Args:
            encrypted: base64编码的密文
            key: 32字节密钥

        Returns:
            明文，失败返回None
        """
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM

            data = base64.b64decode(encrypted)

            # 检查版本
            version = data[0]
            if version != 1:
                raise ValueError(f"不支持的加密版本: {version}")

            nonce = data[1:13]  # 12 bytes nonce
            ciphertext = data[13:]  # 剩余部分是密文+tag

            aesgcm = AESGCM(key)
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
            return plaintext.decode('utf-8')
        except Exception as e:
            print(f"解密失败: {e}")
            return None


class TransportCrypto:
    """传输加密类 - 用于API密钥的安全传输"""

    def __init__(self, transport_key: str):
        """
        初始化传输加密

        Args:
            transport_key: 传输密钥（应该与前端共享）
        """
        self.key = CryptoUtils.derive_key(transport_key)

    def encrypt(self, plaintext: str) -> str:
        """加密数据"""
        return CryptoUtils.encrypt(plaintext, self.key)

    def decrypt(self, encrypted: str) -> Optional[str]:
        """解密数据"""
        return CryptoUtils.decrypt(encrypted, self.key)


# 全局传输密钥 - 用于前后端通信
# 注意: 实际部署时应该通过环境变量或配置文件设置
DEFAULT_TRANSPORT_KEY = "MemOS_Secure_Transport_Key_2026"


def get_transport_crypto(transport_key: Optional[str] = None) -> TransportCrypto:
    """获取传输加密实例"""
    key = transport_key or DEFAULT_TRANSPORT_KEY
    return TransportCrypto(key)
