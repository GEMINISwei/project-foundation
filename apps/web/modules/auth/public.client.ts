/**
 * auth 模組的 Client 公開面 (不含 server-only, server 端也能引用)。
 *
 * 密碼規則由這個模組唯一擁有: 登入、個人設定改密碼、管理者建立使用者與重設密碼
 * 都要套同一條規則, 而它只該有一份實作。
 */

export { MIN_PASSWORD_LENGTH, validateLoginPassword, validateNewPassword } from "./password-policy"
