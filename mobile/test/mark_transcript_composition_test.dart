import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/mark/mark_transcript_composition.dart';

void main() {
  test('recognized speech follows existing Mark text without replacement', () {
    expect(
      appendMarkTranscript('Je prépare une réunion.', '  Inviter le groupe. '),
      'Je prépare une réunion.\nInviter le groupe.',
    );
  });

  test('a new transcription does not remove the previous transcription', () {
    final first = appendMarkTranscript('Début', 'Première idée.');
    expect(
      appendMarkTranscript(first, 'Seconde idée.'),
      'Début\nPremière idée.\nSeconde idée.',
    );
  });

  test('blank recognition preserves the exact draft', () {
    expect(appendMarkTranscript('Texte existant  ', '  '), 'Texte existant  ');
  });

  test('long recognition is not silently truncated to the send limit', () {
    final longText = List.filled(200, 'action').join(' ');
    final merged = appendMarkTranscript('Introduction', longText);
    expect(merged.endsWith(longText), isTrue);
    expect(merged.length, greaterThan(600));
  });

  test(
    'existing whitespace is preserved without inserting extra separator',
    () {
      expect(appendMarkTranscript('Début\n', 'Suite'), 'Début\nSuite');
    },
  );
}
