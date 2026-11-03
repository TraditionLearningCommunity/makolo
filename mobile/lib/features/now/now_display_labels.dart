/// Remove only a repeated context suffix from a presentation label.
/// The owner action/capability is unchanged; this is visual copy only.
String _withoutRepeatedContext(String value, String context) {
  final label = value.trim();
  final subject = context.trim();
  if (subject.isEmpty || label.isEmpty) return label;
  for (final separator in const [' — ', ' – ', ': ']) {
    final suffix = '$separator$subject';
    if (label.length > suffix.length &&
        label.toLowerCase().endsWith(suffix.toLowerCase())) {
      final prefix = label.substring(0, label.length - suffix.length).trim();
      if (prefix.isNotEmpty) return prefix;
    }
  }
  return label;
}

String nowDisplayHeadline(String meaning, String humanContext) =>
    _withoutRepeatedContext(meaning, humanContext);

String nowDisplayActionLabel(String label, String humanContext) =>
    _withoutRepeatedContext(label, humanContext);

String nowDisplayHandoffLabel(
  String label,
  String meaning,
  String humanContext,
) {
  final shortened = nowDisplayActionLabel(label, humanContext);
  return shortened.toLowerCase() ==
          nowDisplayHeadline(meaning, humanContext).toLowerCase()
      ? 'Voir les détails'
      : shortened;
}
