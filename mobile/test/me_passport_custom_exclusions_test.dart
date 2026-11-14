import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/me/me_passport_screen.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';

class _PassportApi implements MakoloApiClient {
  int reads = 0;

  @override
  Uri get baseUri => Uri.parse('https://makolo.invalid/');

  @override
  Future<ApiResponse> get(
    String path, {
    Map<String, String>? headers,
    MakoloCancelHandle? cancel,
  }) async {
    reads++;
    return ApiResponse(
      200,
      jsonEncode({
        'meta': {
          'projection': 'personal.me.passport',
          'scope': 'personal',
          'schema_version': 1,
          'generated_at': '2026-11-03T09:00:00Z',
        },
        'data': {
          'variant': 'complete',
          'identity': {
            'name': 'Amina Exemple',
            'profession': 'Ingénieure',
            'headline': 'Ingénieure',
            'location': 'Kinshasa, CD',
            'avatar_url': '',
            'links': [],
          },
          'private_details': {
            'first_name': 'Amina',
            'country': 'CD',
            'city': 'Kinshasa',
          },
          'declared': {'interests': [], 'open_to': []},
          'activities': [],
          'experiences': [],
          'established': {'proofs': []},
          'issued': {'credentials': []},
          'collectives': {},
          'topic_options': [],
          'composition': {
            'schema_version': 1,
            'public_identity': {
              'name': 'Amina Exemple',
              'profession': 'Ingénieure',
              'headline': 'Ingénieure',
              'location': 'Kinshasa, CD',
              'avatar_url': '',
              'links': [],
              'presentation_details': {
                'username': 'amina',
                'first_name': 'Amina',
                'city': 'Kinshasa',
                'country': 'CD',
              },
            },
            'public_ids': {
              'interests': [],
              'open_to': [],
              'activities': [],
              'experiences': [],
              'proofs': [],
              'credentials': [],
            },
          },
        },
      }),
      const {},
    );
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  testWidgets(
    'custom exclusions remove duplicated professional and location facts',
    (tester) async {
      final api = _PassportApi();
      await tester.pumpWidget(MaterialApp(home: MePassportScreen(api: api)));
      await tester.pumpAndSettle();
      expect(find.text('Ingénieure'), findsOneWidget);
      expect(api.reads, 1);

      await tester.tap(find.text('Personnalisé'));
      await tester.pumpAndSettle();
      expect(find.text('Ingénieure'), findsOneWidget);
      await tester.tap(find.text('Profession').first);
      await tester.pumpAndSettle();
      expect(find.text('Ingénieure'), findsNothing);

      await tester.tap(find.text('Localisation').first);
      await tester.pumpAndSettle();
      expect(find.text('Kinshasa, CD'), findsNothing);
      expect(find.text('Kinshasa'), findsNothing);
      expect(find.text('CD'), findsNothing);
      expect(find.text('Amina Exemple'), findsOneWidget);
      expect(api.reads, 1);
    },
  );
}
