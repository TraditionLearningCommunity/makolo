class MakoloEnvironment {
  const MakoloEnvironment._();

  static const apiBaseUrl = String.fromEnvironment('MAKOLO_API_BASE_URL');

  static Uri? get apiBaseUri {
    final value = apiBaseUrl.trim();
    if (value.isEmpty) return null;
    return Uri.parse(value.endsWith('/') ? value : '$value/');
  }
}
