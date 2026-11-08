import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/me/passport_editor_field_rules.dart';

void main() {
  group('PassportEditorFieldRules', () {
    test('normalizes HTTPS only once, including pasted double schemes', () {
      for (final input in [
        'exemple.com',
        'https://exemple.com',
        'HTTPS://exemple.com',
        'http://exemple.com',
        'https://https://exemple.com',
        ' HTTPS://HTTP://exemple.com ',
      ]) {
        final normalized = PassportEditorFieldRules.normalize('website', input);
        expect(normalized, 'https://exemple.com');
        expect(
          PassportEditorFieldRules.normalize('website', normalized),
          normalized,
        );
        expect(PassportEditorFieldRules.error('website', normalized), isNull);
      }
      expect(PassportEditorFieldRules.error('website', 'exemple'), isNotNull);
      expect(PassportEditorFieldRules.error('website', 'https://'), isNotNull);
      expect(
        PassportEditorFieldRules.error('website', 'javascript:alert(1)'),
        isNotNull,
      );
      expect(
        PassportEditorFieldRules.error(
          'website',
          'https://user:password@exemple.com',
        ),
        isNotNull,
      );
    });

    test('website and social fields accept only matching safe hosts', () {
      expect(
        PassportEditorFieldRules.error('linkedin_url', 'linkedin.com/in/amina'),
        isNull,
      );
      expect(
        PassportEditorFieldRules.error(
          'linkedin_url',
          'https://evil-linkedin.com/in/amina',
        ),
        isNotNull,
      );
      expect(
        PassportEditorFieldRules.error(
          'facebook_url',
          'www.facebook.com/amina',
        ),
        isNull,
      );
      expect(
        PassportEditorFieldRules.error('instagram_url', 'instagram.com/amina'),
        isNull,
      );
      expect(
        PassportEditorFieldRules.error('tiktok_url', 'tiktok.com/@amina'),
        isNull,
      );
      expect(
        PassportEditorFieldRules.error('x_url', 'twitter.com/amina'),
        isNull,
      );
      expect(PassportEditorFieldRules.error('x_url', 'x.com/amina'), isNull);
      expect(
        PassportEditorFieldRules.error('youtube_url', 'youtu.be/AbCd12'),
        isNull,
      );
      expect(
        PassportEditorFieldRules.error('youtube_url', 'youtube.com/@amina'),
        isNull,
      );
      expect(
        PassportEditorFieldRules.error(
          'website',
          'https://exemple.com/une page',
        ),
        isNotNull,
      );
    });

    test('phone validates punctuation, digits and field bound locally', () {
      expect(
        PassportEditorFieldRules.error('phone', '+243 810-000-000'),
        isNull,
      );
      expect(
        PassportEditorFieldRules.error('phone', '(+243) 810 000 000'),
        isNotNull,
      ); // Plus sign is only valid at the beginning.
      expect(
        PassportEditorFieldRules.error('phone', '123456'),
        '7 à 15 chiffres.',
      );
      expect(
        PassportEditorFieldRules.error('phone', '1234567890123456'),
        '7 à 15 chiffres.',
      );
      expect(PassportEditorFieldRules.error('phone', '+243ABC0000'), isNotNull);
      expect(PassportEditorFieldRules.error('phone', ''), isNull);
    });

    test('lengths agree with Accounts without inventing bio limits', () {
      expect(
        PassportEditorFieldRules.error(
          'first_name',
          List.filled(151, 'a').join(),
        ),
        isNotNull,
      );
      expect(
        PassportEditorFieldRules.error(
          'profession',
          List.filled(256, 'a').join(),
        ),
        isNotNull,
      );
      expect(
        PassportEditorFieldRules.error('city', List.filled(101, 'a').join()),
        isNotNull,
      );
      expect(
        PassportEditorFieldRules.error(
          'website',
          'exemple.com/${List.filled(220, 'a').join()}',
        ),
        isNotNull,
      );
      expect(
        PassportEditorFieldRules.error('bio', List.filled(3000, 'x').join()),
        isNull,
      );
    });

    test('identifier normalizes locally and keeps server-only uniqueness', () {
      expect(
        PassportEditorFieldRules.normalize('username', ' @Amina_001 '),
        'amina_001',
      );
      expect(PassportEditorFieldRules.error('username', '@Amina_001'), isNull);
      expect(PassportEditorFieldRules.error('username', 'ab'), isNotNull);
      expect(
        PassportEditorFieldRules.error('username', 'admin'),
        'Identifiant réservé.',
      );
      expect(PassportEditorFieldRules.error('username', '_amina'), isNotNull);
      expect(PassportEditorFieldRules.error('username', 'amina.'), isNotNull);
    });

    test('date rejects impossible days and future dates', () {
      expect(
        PassportEditorFieldRules.error('birth_date', '2000-02-29'),
        isNull,
      );
      expect(
        PassportEditorFieldRules.error('birth_date', '2001-02-29'),
        isNotNull,
      );
      expect(
        PassportEditorFieldRules.error('birth_date', '2999-01-01'),
        isNotNull,
      );
      expect(PassportEditorFieldRules.error('birth_date', ''), isNull);
    });
  });
}
