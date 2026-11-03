import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/me/me_passport_screen.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';

class _Stage3PassportApi implements MakoloApiClient {
  @override
  Uri get baseUri => Uri.parse('https://example.test/');

  @override
  Future<ApiResponse> get(
    String path, {
    Map<String, String>? headers,
    MakoloCancelHandle? cancel,
  }) async {
    return ApiResponse(
      200,
      jsonEncode({
        'meta': {
          'projection': 'personal.me.passport',
          'schema_version': 1,
          'scope': 'personal',
          'generated_at': '2026-11-02T10:00:00Z',
        },
        'data': {
          'variant': 'complete',
          'identity': {
            'name': 'Profil exemple',
            'avatar_url': '',
            'links': const [],
          },
          'declared': {
            'interests': const [],
            'open_to': [
              {
                'id': 'a',
                'kind': 'mentor',
                'label': 'Mentorat',
                'topic': {'code': 'geometry', 'label': 'Géométrie'},
              },
              {
                'id': 'b',
                'kind': 'mentor',
                'label': 'Mentorat',
                'topic': {'code': 'research', 'label': 'Recherche'},
              },
            ],
          },
          'activities': const [],
          'established': {'proofs': const []},
          'issued': {'credentials': const []},
          'collectives': const {},
          'topic_options': const [],
        },
      }),
      const {},
    );
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  testWidgets('Passport preserves each Open To topic in native presentation', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(home: MePassportScreen(api: _Stage3PassportApi())),
    );
    await tester.pumpAndSettle();
    expect(find.text('Mentorat · Géométrie'), findsOneWidget);
    expect(find.text('Mentorat · Recherche'), findsOneWidget);
    expect(find.text('Mentorat'), findsNothing);
  });
}
