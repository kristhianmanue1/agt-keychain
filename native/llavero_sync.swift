import Foundation
import Security

// Build and sign as a provisioned macOS app helper with a stable access group.
// Requests and responses use JSON over pipes. Secret bytes never enter argv.
private let services = [
    "secret": "llavero.sync.secret.v1",
    "profile": "llavero.sync.profile.v1",
]
private let identifierPattern = try! NSRegularExpression(pattern: "^[a-z0-9][a-z0-9._-]{0,62}$")

private func emit(_ value: [String: Any], status: Int32 = 0) -> Never {
    if let data = try? JSONSerialization.data(withJSONObject: value, options: [.sortedKeys]),
       let line = String(data: data, encoding: .utf8) {
        print(line)
    } else {
        print("{\"ok\":false,\"error\":\"serialization\"}")
    }
    exit(status)
}

private func failure(_ code: String, _ status: OSStatus? = nil) -> Never {
    var response: [String: Any] = ["ok": false, "error": code]
    if let status = status { response["status"] = Int(status) }
    emit(response, status: 1)
}

private func validIdentifier(_ value: String) -> Bool {
    let range = NSRange(value.startIndex..<value.endIndex, in: value)
    return identifierPattern.firstMatch(in: value, range: range)?.range == range
}

private let input = FileHandle.standardInput.readData(ofLength: 65537)
if input.count > 65536 { failure("request_too_large") }
guard let request = (try? JSONSerialization.jsonObject(with: input)) as? [String: Any],
      let operation = request["operation"] as? String,
      let kind = request["kind"] as? String,
      let service = services[kind] else { failure("invalid_request") }

if operation == "list" {
    let query: [String: Any] = [
        kSecClass as String: kSecClassGenericPassword,
        kSecAttrService as String: service,
        kSecAttrSynchronizable as String: true,
        kSecReturnAttributes as String: true,
        kSecMatchLimit as String: kSecMatchLimitAll,
    ]
    var result: CFTypeRef?
    let status = SecItemCopyMatching(query as CFDictionary, &result)
    if status == errSecItemNotFound { emit(["ok": true, "identifiers": []]) }
    if status != errSecSuccess { failure("keychain_error", status) }
    guard let records = result as? [[String: Any]] else { failure("invalid_keychain_result") }
    let identifiers = records.compactMap { $0[kSecAttrAccount as String] as? String }
        .filter(validIdentifier).sorted()
    emit(["ok": true, "identifiers": identifiers])
}

guard let identifier = request["identifier"] as? String,
      validIdentifier(identifier) else { failure("invalid_identifier") }
let query: [String: Any] = [
    kSecClass as String: kSecClassGenericPassword,
    kSecAttrService as String: service,
    kSecAttrAccount as String: identifier,
    kSecAttrSynchronizable as String: true,
]

switch operation {
case "exists", "get":
    var lookup = query
    lookup[kSecMatchLimit as String] = kSecMatchLimitOne
    lookup[(operation == "get" ? kSecReturnData : kSecReturnAttributes) as String] = true
    var result: CFTypeRef?
    let status = SecItemCopyMatching(lookup as CFDictionary, &result)
    if status == errSecItemNotFound { emit(["ok": true, "found": false]) }
    if status != errSecSuccess { failure("keychain_error", status) }
    if operation == "exists" { emit(["ok": true, "found": true]) }
    guard let data = result as? Data else { failure("invalid_keychain_result") }
    emit(["ok": true, "found": true, "data": data.base64EncodedString()])
case "put":
    guard let encoded = request["data"] as? String,
          let data = Data(base64Encoded: encoded),
          !data.isEmpty, data.count <= 16384,
          let replace = request["replace"] as? Bool else { failure("invalid_data") }
    var attributes = query
    attributes[kSecValueData as String] = data
    let status = SecItemAdd(attributes as CFDictionary, nil)
    if status == errSecSuccess { emit(["ok": true]) }
    if status == errSecDuplicateItem && replace {
        let updated = SecItemUpdate(query as CFDictionary,
                                    [kSecValueData as String: data] as CFDictionary)
        if updated == errSecSuccess { emit(["ok": true]) }
        failure("keychain_error", updated)
    }
    if status == errSecDuplicateItem { failure("already_exists") }
    failure("keychain_error", status)
case "delete":
    let status = SecItemDelete(query as CFDictionary)
    if status == errSecSuccess { emit(["ok": true, "deleted": true]) }
    if status == errSecItemNotFound { emit(["ok": true, "deleted": false]) }
    failure("keychain_error", status)
default:
    failure("invalid_operation")
}
