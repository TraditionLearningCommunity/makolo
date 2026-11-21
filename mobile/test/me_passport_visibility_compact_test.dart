import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/me/me_passport_visibility_screen.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';

class _VisibilityApi implements MakoloApiClient {
  Map<String, dynamic>? updated;

  @override
  Future<ApiResponse> get(
    String path, {
    Map<String, String>? headers,
    MakoloCancelHandle? cancel,
  }) async => _envelope();

  @override
  Future<ApiResponse> put(
    String path, {
    Map<String, dynamic>? body,
    Map<String, String>? headers,
    MakoloCancelHandle? cancel,
  }) async {
    updated = body;
    return _envelope();
  }

  ApiResponse _envelope() => ApiResponse(
    200,
    jsonEncode({
      'meta': {
        'projection': 'personal.me.passport.visibility',
        'schema_version': 1,
        'scope': 'personal',
        'generated_at': '2026-11-02T10:00:00Z',
      },
      'data': {
        'fields': {
          'name': {
            'audiences': [
              {'kind': 'public'},
            ],
            'has_value': true,
          },
          'linkedin_url': {
            'audiences': [
              {'kind': 'public'},
            ],
            'has_value': false,
          },
        },
        'collectives': {'spaces': [], 'teams': [], 'groups': []},
        'interests': [],
        'open_to': [],
      },
    }),
    const {},
  );

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  testWidgets(
    'blank public settings are grouped instead of posing as content',
    (tester) async {
      final api = _VisibilityApi();
      await tester.pumpWidget(
        MaterialApp(home: MePassportVisibilityScreen(api: api)),
      );
      await tester.pumpAndSettle();

      expect(find.text('Nom'), findsOneWidget);
      expect(find.text('Informations à renseigner'), findsOneWidget);
      expect(find.text('LinkedIn'), findsNothing);
      await tester.tap(find.text('Informations à renseigner'));
      await tester.pumpAndSettle();
      expect(find.text('LinkedIn'), findsOneWidget);
    },
  );

  testWidgets('one compact choice can make the field private', (tester) async {
    final api = _VisibilityApi();
    await tester.pumpWidget(
      MaterialApp(home: MePassportVisibilityScreen(api: api)),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Nom'));
    await tester.pumpAndSettle();
    expect(find.text('Tout le monde'), findsOneWidget);
    expect(find.text('Choisir des personnes ou collectifs'), findsOneWidget);
    await tester.tap(find.text('Moi uniquement').last);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Enregistrer'));
    await tester.pumpAndSettle();
    expect(api.updated?['target_kind'], 'field');
    expect(api.updated?['field_key'], 'name');
    expect(api.updated?['audiences'], isEmpty);
  });
}
