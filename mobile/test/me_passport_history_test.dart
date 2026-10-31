import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/me/me_passport_screen.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';

const _versionId = '11111111-1111-4111-8111-111111111111';

class _DatedPassportApi implements MakoloApiClient {
  @override
  Uri get baseUri => Uri.parse('https://example.test/');

  ApiResponse _envelope(String projection, Map<String, dynamic> data) =>
      ApiResponse(
        200,
        jsonEncode({
          'meta': {
            'projection': projection,
            'schema_version': 1,
            'scope': 'personal',
            'generated_at': '2026-10-30T12:00:00Z',
          },
          'data': data,
        }),
        const {},
      );

  @override
  Future<ApiResponse> get(
    String path, {
    Map<String, String>? headers,
    MakoloCancelHandle? cancel,
  }) async {
    if (path.contains('passport/history/$_versionId/')) {
      return _envelope('personal.me.passport.version', {
        'id': _versionId,
        'document_id': 'PM-P-20261030-11111111',
        'variant': 'complete',
        'generated_at': '2026-10-30T10:00:00Z',
        'payload': {
          'identity': {
            'name': 'Profil exemple',
            'bio': 'Présentation telle qu’émise.',
            'location': 'Lubumbashi',
            'links': const [],
            'owner_details': const {},
          },
          'interests': ['Recherche'],
          'open_to': const [],
          'activities': const [],
          'proofs': const [],
          'credentials': const [],
          'team_affiliations': const [],
          'active_space_mandates': const [],
        },
      });
    }
    if (path.contains('passport/history/')) {
      return _envelope('personal.me.passport.history', {
        'count': 1,
        'has_more': false,
        'next_offset': 1,
        'items': [
          {
            'id': _versionId,
            'document_id': 'PM-P-20261030-11111111',
            'variant': 'complete',
            'generated_at': '2026-10-30T10:00:00Z',
            'revoked': false,
            'integrity_ok': true,
          },
        ],
      });
    }
    return _envelope('personal.me.passport', {
      'variant': 'complete',
      'identity': {
        'name': 'Profil exemple',
        'bio': 'Présentation actuellement mise à jour.',
        'avatar_url': '',
        'links': const [],
      },
      'declared': {'interests': const [], 'open_to': const []},
      'activities': const [],
      'established': {'proofs': const []},
      'issued': {'credentials': const []},
    });
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  testWidgets(
    'dated Passport opens the issued content instead of live content',
    (tester) async {
      await tester.pumpWidget(
        MaterialApp(home: MePassportScreen(api: _DatedPassportApi())),
      );
      await tester.pumpAndSettle();
      expect(
        find.text('Présentation actuellement mise à jour.'),
        findsOneWidget,
      );
      await tester.tap(find.byTooltip('Versions datées'));
      await tester.pumpAndSettle();
      expect(find.text('PM-P-20261030-11111111'), findsOneWidget);
      await tester.tap(find.text('PM-P-20261030-11111111'));
      await tester.pumpAndSettle();
      expect(find.text('Présentation telle qu’émise.'), findsOneWidget);
      expect(find.text('Recherche'), findsOneWidget);
    },
  );
}
