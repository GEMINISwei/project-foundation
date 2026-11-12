/**
 * roles 模組的 Client 公開面。
 *
 * `getRoleDisplayName` 由這個模組唯一擁有: users 模組的列表也要顯示角色名稱,
 * 而「系統角色走字典、其他角色用 DB 名稱」這條規則只該有一份實作。
 * 字典也一起轉出 —— 呼叫端需要用它建出 translator 才能查到系統角色的名稱。
 */

export { getRoleDisplayName } from "./constants"
export { rolesMessages } from "./i18n"
