#include "cx_vision/runtime_contracts.hpp"

#include <cctype>
#include <fstream>
#include <sstream>

namespace cx_vision {

namespace {

std::string EscapeJsonString(const std::string& s) {
    std::ostringstream escaped;
    for (char c : s) {
        switch (c) {
            case '"':  escaped << "\\\""; break;
            case '\\': escaped << "\\\\"; break;
            case '\b': escaped << "\\b";  break;
            case '\f': escaped << "\\f";  break;
            case '\n': escaped << "\\n";  break;
            case '\r': escaped << "\\r";  break;
            case '\t': escaped << "\\t";  break;
            default:
                if (static_cast<unsigned char>(c) < 0x20) {
                    escaped << "\\u00" << "0123456789abcdef"[(c >> 4) & 0xf]
                            << "0123456789abcdef"[c & 0xf];
                } else {
                    escaped << c;
                }
                break;
        }
    }
    return escaped.str();
}

// Extract the JSON string value for a given key from raw content.
// Handles "key": "value" and "key":"value" (whitespace after colon tolerated).
// Returns empty string if key is not found or value is not a quoted string.
std::string ExtractJsonString(const std::string& content, const std::string& key) {
    std::string search = "\"" + key + "\"";
    auto pos = content.find(search);
    if (pos == std::string::npos) return "";
    pos += search.size();
    pos = content.find(":", pos);
    if (pos == std::string::npos) return "";
    ++pos;
    while (pos < content.size()
           && std::isspace(static_cast<unsigned char>(content[pos])) != 0) {
        ++pos;
    }
    if (pos >= content.size() || content[pos] != '"') return "";
    ++pos;
    auto end = content.find("\"", pos);
    if (end == std::string::npos) return "";
    return content.substr(pos, end - pos);
}

void SkipWhitespaceAt(const std::string& content, std::size_t& pos) {
    while (pos < content.size()
           && std::isspace(static_cast<unsigned char>(content[pos])) != 0) {
        ++pos;
    }
}

std::string ReadQuotedStringAt(const std::string& content, std::size_t& pos) {
    if (pos >= content.size() || content[pos] != '"') return "";
    ++pos;
    std::string value;
    while (pos < content.size()) {
        char c = content[pos++];
        if (c == '"') {
            return value;
        }
        if (c == '\\') {
            if (pos >= content.size()) return "";
            // Preserve escaped characters as their escaped payload. The config
            // required fields are identifiers, so full unicode decoding is not
            // needed for contract validation.
            value.push_back(content[pos++]);
            continue;
        }
        value.push_back(c);
    }
    return "";
}

bool SkipQuotedStringAt(const std::string& content, std::size_t& pos) {
    if (pos >= content.size() || content[pos] != '"') return false;
    ++pos;
    while (pos < content.size()) {
        char c = content[pos++];
        if (c == '"') return true;
        if (c == '\\') {
            if (pos >= content.size()) return false;
            ++pos;
        }
    }
    return false;
}

bool SkipJsonValueAt(const std::string& content, std::size_t& pos) {
    SkipWhitespaceAt(content, pos);
    if (pos >= content.size()) return false;

    if (content[pos] == '"') {
        return SkipQuotedStringAt(content, pos);
    }

    if (content[pos] == '{' || content[pos] == '[') {
        const char open = content[pos];
        const char close = open == '{' ? '}' : ']';
        int depth = 1;
        ++pos;
        bool in_string = false;
        while (pos < content.size()) {
            char c = content[pos++];
            if (in_string) {
                if (c == '\\') {
                    if (pos >= content.size()) return false;
                    ++pos;
                    continue;
                }
                if (c == '"') {
                    in_string = false;
                }
                continue;
            }
            if (c == '"') {
                in_string = true;
            } else if (c == open) {
                ++depth;
            } else if (c == close) {
                --depth;
                if (depth == 0) return true;
            }
        }
        return false;
    }

    while (pos < content.size()
           && content[pos] != ','
           && content[pos] != '}') {
        ++pos;
    }
    return true;
}

std::string ExtractTopLevelJsonString(
    const std::string& content,
    const std::string& target_key
) {
    std::size_t pos = 0;
    SkipWhitespaceAt(content, pos);
    if (pos >= content.size() || content[pos] != '{') return "";
    ++pos;

    while (pos < content.size()) {
        SkipWhitespaceAt(content, pos);
        if (pos < content.size() && content[pos] == '}') return "";

        std::string key = ReadQuotedStringAt(content, pos);
        if (key.empty()) return "";

        SkipWhitespaceAt(content, pos);
        if (pos >= content.size() || content[pos] != ':') return "";
        ++pos;
        SkipWhitespaceAt(content, pos);

        if (key == target_key) {
            return ReadQuotedStringAt(content, pos);
        }
        if (!SkipJsonValueAt(content, pos)) return "";

        SkipWhitespaceAt(content, pos);
        if (pos < content.size() && content[pos] == ',') {
            ++pos;
            continue;
        }
        if (pos < content.size() && content[pos] == '}') {
            return "";
        }
    }
    return "";
}

// Returns the first non-whitespace character of the value for target_key,
// or '\0' if the key is not found.
char FindTopLevelValueFirstChar(const std::string& content, const std::string& target_key) {
    std::size_t pos = 0;
    SkipWhitespaceAt(content, pos);
    if (pos >= content.size() || content[pos] != '{') return '\0';
    ++pos;  // skip '{'

    while (pos < content.size()) {
        SkipWhitespaceAt(content, pos);
        if (pos < content.size() && content[pos] == '}') return '\0';  // end of object

        std::string key = ReadQuotedStringAt(content, pos);
        if (key.empty()) return '\0';

        SkipWhitespaceAt(content, pos);
        if (pos >= content.size() || content[pos] != ':') return '\0';
        ++pos;  // skip ':'
        SkipWhitespaceAt(content, pos);

        if (key == target_key) {
            if (pos >= content.size()) return '\0';
            return content[pos];
        }

        // Skip this value
        if (!SkipJsonValueAt(content, pos)) return '\0';

        SkipWhitespaceAt(content, pos);
        if (pos < content.size() && content[pos] == ',') {
            ++pos;
            continue;
        }
        if (pos < content.size() && content[pos] == '}') {
            return '\0';  // key not found
        }
    }
    return '\0';
}

// --- Strict recursive-descent JSON parser for flat-object validation ----------
//
// Encoder / Decoder / Validator, but only the Validator path is used for
// config-file checking.  The parser handles objects, arrays, strings, numbers,
// booleans and null.  It rejects:
//   - missing commas between object members / array elements
//   - trailing commas
//   - unquoted keys
//   - garbage before the opening brace or after the closing brace
//   - unbalanced braces / brackets
//   - unterminated strings
//   - invalid escape sequences
//
// Architecture note: this is intentionally self-contained (no third-party
// dependency). It validates JSON objects; required fields are then read only
// from top-level string members.


namespace {

class JsonValidator {
 public:
    explicit JsonValidator(const std::string& input)
        : s_(input), pos_(0) {}

    bool ValidateObject() {
        SkipWhitespace();
        if (!Expect('{')) return false;
        SkipWhitespace();
        if (Peek() == '}') {
            Advance();  // empty object "{}"
            return SkipTrailingWhitespace();
        }
        // Parse members.
        if (!ParseMember()) return false;
        SkipWhitespace();
        while (Peek() == ',') {
            Advance();          // consume ','
            SkipWhitespace();
            if (!ParseMember()) return false;
            SkipWhitespace();
        }
        if (!Expect('}')) return false;
        return SkipTrailingWhitespace();
    }

 private:
    const std::string& s_;
    std::size_t pos_;

    // -- primitives ---------------------------------------------------------

    char Peek() const {
        if (pos_ < s_.size()) return s_[pos_];
        return '\0';
    }

    char Advance() {
        if (pos_ < s_.size()) return s_[pos_++];
        return '\0';
    }

    bool Match(char c) {
        if (Peek() == c) { Advance(); return true; }
        return false;
    }

    bool Expect(char c) {
        if (Match(c)) return true;
        return false;
    }

    void SkipWhitespace() {
        while (pos_ < s_.size()
               && std::isspace(static_cast<unsigned char>(s_[pos_])) != 0) {
            ++pos_;
        }
    }

    bool SkipTrailingWhitespace() {
        while (pos_ < s_.size()) {
            if (std::isspace(static_cast<unsigned char>(s_[pos_])) == 0) {
                return false;  // trailing garbage
            }
            ++pos_;
        }
        return true;
    }

    // -- member ::= string ':' value ---------------------------------------

    bool ParseMember() {
        if (!ParseString()) return false;
        SkipWhitespace();
        if (!Expect(':')) return false;
        SkipWhitespace();
        return ParseValue();
    }

    // -- value ::= string | number | object | array | true | false | null ---

    bool ParseValue() {
        char c = Peek();
        if (c == '"') {
            return ParseString();
        }
        if (c == '-' || (c >= '0' && c <= '9')) {
            return ParseNumber();
        }
        if (c == '{') {
            return ParseObjectBody();
        }
        if (c == '[') {
            return ParseArray();
        }
        if (c == 't') {
            return ParseLiteral("true", 4);
        }
        if (c == 'f') {
            return ParseLiteral("false", 5);
        }
        if (c == 'n') {
            return ParseLiteral("null", 4);
        }
        return false;  // unexpected character
    }

    // -- string -------------------------------------------------------------

    bool ParseString() {
        if (!Expect('"')) return false;
        while (pos_ < s_.size()) {
            char c = Advance();
            if (c == '"') return true;   // closing quote
            if (c == '\\') {
                if (pos_ >= s_.size()) return false;  // nothing after backslash
                char esc = Advance();
                switch (esc) {
                    case '"': case '\\': case '/':
                    case 'b': case 'f': case 'n': case 'r': case 't':
                        break;
                    case 'u':
                        // Expect 4 hex digits.
                        for (int i = 0; i < 4; ++i) {
                            if (pos_ >= s_.size()) return false;
                            char h = Advance();
                            bool is_hex = (h >= '0' && h <= '9')
                                       || (h >= 'a' && h <= 'f')
                                       || (h >= 'A' && h <= 'F');
                            if (!is_hex) return false;
                        }
                        break;
                    default:
                        return false;  // invalid escape
                }
            }
            // Unescaped control characters are invalid in JSON strings.
            if (static_cast<unsigned char>(c) < 0x20) return false;
        }
        return false;  // unterminated string
    }

    // -- number (integer / float / scientific) -------------------------------

    bool ParseNumber() {
        std::size_t start = pos_;
        if (Peek() == '-') Advance();
        if (Peek() == '0') {
            Advance();
        } else if (Peek() >= '1' && Peek() <= '9') {
            while (Peek() >= '0' && Peek() <= '9') Advance();
        } else {
            return false;  // no valid digit
        }
        // fraction
        if (Peek() == '.') {
            Advance();
            if (!(Peek() >= '0' && Peek() <= '9')) return false;
            while (Peek() >= '0' && Peek() <= '9') Advance();
        }
        // exponent
        if (Peek() == 'e' || Peek() == 'E') {
            Advance();
            if (Peek() == '+' || Peek() == '-') Advance();
            if (!(Peek() >= '0' && Peek() <= '9')) return false;
            while (Peek() >= '0' && Peek() <= '9') Advance();
        }
        return pos_ > start;  // consumed at least one digit
    }

    // -- literal ( true / false / null ) ------------------------------------

    bool ParseLiteral(const char* expected, std::size_t len) {
        for (std::size_t i = 0; i < len; ++i) {
            if (Peek() != expected[i]) return false;
            Advance();
        }
        return true;
    }

    // -- object (nested) ----------------------------------------------------

    bool ParseObjectBody() {
        if (!Expect('{')) return false;
        SkipWhitespace();
        if (Peek() == '}') {
            Advance();
            return true;
        }
        if (!ParseMember()) return false;
        SkipWhitespace();
        while (Peek() == ',') {
            Advance();
            SkipWhitespace();
            if (!ParseMember()) return false;
            SkipWhitespace();
        }
        return Expect('}');
    }

    // -- array ---------------------------------------------------------------

    bool ParseArray() {
        if (!Expect('[')) return false;
        SkipWhitespace();
        if (Peek() == ']') {
            Advance();
            return true;
        }
        if (!ParseValue()) return false;
        SkipWhitespace();
        while (Peek() == ',') {
            Advance();
            SkipWhitespace();
            if (!ParseValue()) return false;
            SkipWhitespace();
        }
        return Expect(']');
    }
};

}  // namespace (validator helpers)

}  // namespace

bool ValidateMinimalJsonObject(const std::string& content) {
    JsonValidator v(content);
    return v.ValidateObject();
}

namespace {

// Returns true if every entry in the cameras array begins with '{'.
// Returns true if cameras key is absent or array is empty '[]'.
bool TopLevelArrayObjectsOnly(const std::string& content, const std::string& target_key) {
    std::size_t pos = 0;
    SkipWhitespaceAt(content, pos);
    if (pos >= content.size() || content[pos] != '{') return false;
    ++pos;

    while (pos < content.size()) {
        SkipWhitespaceAt(content, pos);
        if (pos < content.size() && content[pos] == '}') return true;

        std::string key = ReadQuotedStringAt(content, pos);
        if (key.empty()) return false;
        SkipWhitespaceAt(content, pos);
        if (pos >= content.size() || content[pos] != ':') return false;
        ++pos;
        SkipWhitespaceAt(content, pos);

        if (key == target_key) {
            if (pos >= content.size()) return false;
            if (content[pos] != '[') return false;
            ++pos;  // skip '['
            SkipWhitespaceAt(content, pos);
            if (content[pos] == ']') return true;  // empty array OK
            // Each element must start with '{'
            while (pos < content.size()) {
                SkipWhitespaceAt(content, pos);
                if (pos < content.size() && content[pos] == ']') return true;
                if (pos >= content.size() || content[pos] != '{') return false;
                if (!SkipJsonValueAt(content, pos)) return false;
                SkipWhitespaceAt(content, pos);
                if (pos < content.size() && content[pos] == ',') {
                    ++pos;
                }
            }
            return false;
        }

        if (!SkipJsonValueAt(content, pos)) return false;
        SkipWhitespaceAt(content, pos);
        if (pos < content.size() && content[pos] == ',') { ++pos; continue; }
        if (pos < content.size() && content[pos] == '}') return true;
        return false;
    }
    return false;
}

// Returns true if every value in the model_artifacts object begins with '"'.
// Returns true if model_artifacts key is absent or object is empty '{}'.
bool TopLevelObjectStringValuesOnly(const std::string& content, const std::string& target_key) {
    std::size_t pos = 0;
    SkipWhitespaceAt(content, pos);
    if (pos >= content.size() || content[pos] != '{') return false;
    ++pos;

    while (pos < content.size()) {
        SkipWhitespaceAt(content, pos);
        if (pos < content.size() && content[pos] == '}') return true;

        std::string key = ReadQuotedStringAt(content, pos);
        if (key.empty()) return false;
        SkipWhitespaceAt(content, pos);
        if (pos >= content.size() || content[pos] != ':') return false;
        ++pos;
        SkipWhitespaceAt(content, pos);

        if (key == target_key) {
            if (pos >= content.size()) return false;
            if (content[pos] != '{') return false;
            ++pos;  // skip '{'
            SkipWhitespaceAt(content, pos);
            if (content[pos] == '}') return true;  // empty object OK
            // Each value under model_artifacts must be a string
            while (pos < content.size()) {
                // Read inner key
                SkipWhitespaceAt(content, pos);
                if (pos < content.size() && content[pos] == '}') return true;
                std::string inner_key = ReadQuotedStringAt(content, pos);
                if (inner_key.empty()) return false;

                SkipWhitespaceAt(content, pos);
                if (pos >= content.size() || content[pos] != ':') return false;
                ++pos;  // skip ':'
                SkipWhitespaceAt(content, pos);

                // Value must be a string
                if (pos >= content.size() || content[pos] != '"') return false;
                if (!SkipQuotedStringAt(content, pos)) return false;

                SkipWhitespaceAt(content, pos);
                if (pos < content.size() && content[pos] == ',') { ++pos; continue; }
                if (pos < content.size() && content[pos] == '}') { continue; }
                return false;
            }
            return false;
        }

        if (!SkipJsonValueAt(content, pos)) return false;
        SkipWhitespaceAt(content, pos);
        if (pos < content.size() && content[pos] == ',') { ++pos; continue; }
        if (pos < content.size() && content[pos] == '}') return true;
        return false;
    }
    return false;
}

}  // namespace

std::string ToJsonLine(const RuntimeStatus& status) {
    std::ostringstream out;
    out << "{\"state\":\"" << EscapeJsonString(status.state) << "\""
        << ",\"uptime_ms\":" << status.uptime_ms
        << ",\"queue_size\":" << status.queue_size
        << ",\"dropped_frames\":" << status.dropped_frames
        << ",\"ng_count\":" << status.ng_count
        << ",\"error_code\":\"" << EscapeJsonString(status.error_code) << "\""
        << ",\"error_message\":\"" << EscapeJsonString(status.error_message) << "\""
        << "}";
    return out.str();
}

std::string ToJsonLine(const DefectEvent& event) {
    std::ostringstream out;
    out << "{\"event_id\":\"" << EscapeJsonString(event.event_id) << "\""
        << ",\"run_id\":\"" << EscapeJsonString(event.run_id) << "\""
        << ",\"camera_id\":\"" << EscapeJsonString(event.camera_id) << "\""
        << ",\"timestamp_ms\":" << event.timestamp_ms
        << ",\"meter_position\":" << event.meter_position
        << ",\"defect_type\":\"" << EscapeJsonString(event.defect_type) << "\""
        << ",\"confidence\":" << event.confidence
        << ",\"bbox_xyxy\":[";
    for (std::size_t i = 0; i < event.bbox_xyxy.size(); ++i) {
        if (i != 0) {
            out << ",";
        }
        out << event.bbox_xyxy[i];
    }
    out << "]"
        << ",\"image_path\":\"" << EscapeJsonString(event.image_path) << "\""
        << ",\"model_version\":\"" << EscapeJsonString(event.model_version) << "\""
        << "}";
    return out.str();
}

RuntimeStatus ReadStateFile(const std::string& path) {
    RuntimeStatus status;
    status.state = "error";
    status.error_code = "STATE_FILE_MISSING";
    status.error_message = path;

    std::ifstream in(path);
    if (!in.is_open()) {
        return status;  // STATE_FILE_MISSING
    }

    // File exists, so parse failures below are invalid-state errors.
    status.error_code = "STATE_FILE_INVALID";

    std::string content;
    {
        std::ostringstream buf;
        buf << in.rdbuf();
        content = buf.str();
    }

    std::string state_val = ExtractJsonString(content, "state");
    if (state_val.empty()) {
        return status;  // STATE_FILE_INVALID
    }

    status.state = state_val;
    status.error_code = "";
    status.error_message = "";
    return status;
}

bool WriteStateFile(const std::string& path, const RuntimeStatus& status) {
    std::ofstream out(path, std::ios::trunc);
    if (!out.is_open()) {
        return false;
    }
    out << ToJsonLine(status) << '\n';
    return out.good();
}

RuntimeConfigSummary ReadRuntimeConfigFile(const std::string& path) {
    RuntimeConfigSummary summary;
    summary.error_code = "CONFIG_FILE_MISSING";
    summary.error_message = path;

    std::ifstream in(path);
    if (!in.is_open()) {
        return summary;  // CONFIG_FILE_MISSING
    }

    // File exists, so parse failures below are invalid errors.
    summary.error_code = "CONFIG_FILE_INVALID";

    std::string content;
    {
        std::ostringstream buf;
        buf << in.rdbuf();
        content = buf.str();
    }

    // Validate JSON structure before extracting fields.
    if (!ValidateMinimalJsonObject(content)) {
        return summary;  // CONFIG_FILE_INVALID
    }

    // Validate top-level structure: cameras must be array, model_artifacts must be object
    char cameras_type = FindTopLevelValueFirstChar(content, "cameras");
    if (cameras_type != '\0' && cameras_type != '[') {
        return summary;  // CONFIG_FILE_INVALID
    }

    char artifacts_type = FindTopLevelValueFirstChar(content, "model_artifacts");
    if (artifacts_type != '\0' && artifacts_type != '{') {
        return summary;  // CONFIG_FILE_INVALID
    }

    // Validate element types: cameras entries must be objects, model_artifacts values must be strings
    if (!TopLevelArrayObjectsOnly(content, "cameras")) {
        return summary;  // CONFIG_FILE_INVALID
    }
    if (!TopLevelObjectStringValuesOnly(content, "model_artifacts")) {
        return summary;  // CONFIG_FILE_INVALID
    }

    summary.run_id = ExtractTopLevelJsonString(content, "run_id");
    summary.project_id = ExtractTopLevelJsonString(content, "project_id");
    summary.spec_id = ExtractTopLevelJsonString(content, "spec_id");
    summary.backend = ExtractTopLevelJsonString(content, "backend");

    if (summary.run_id.empty() || summary.project_id.empty()
        || summary.spec_id.empty() || summary.backend.empty()) {
        return summary;  // CONFIG_FILE_INVALID
    }

    summary.valid = true;
    summary.error_code = "";
    summary.error_message = "";
    return summary;
}

}  // namespace cx_vision
