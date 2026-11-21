/// Append recognized speech to a Mark draft without discarding existing work.
/// This operation belongs to the composer, not to the audio engine.
String appendMarkTranscript(String existing, String recognized) {
  final addition = recognized.trim();
  if (addition.isEmpty) return existing;
  if (existing.isEmpty) return addition;
  final separator = RegExp(r'\s).hasMatch(existing) ? '' : '\n';
  return '$existing$separator$addition';
}
).hasMatch(existing) ? '' : '\n';
  return '$existing$separator$addition';
}
