import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/app/runtime/app_runtime.dart';
import 'package:makolo_mobile/features/me/passport_document_reader_screen.dart';
import 'package:makolo_mobile/navigation/deep_link_resolver.dart';
import 'package:makolo_mobile/navigation/destination.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';

ApiResponse _documentEnvelope({
  required bool explicit,
  required bool readable,
  bool revoked = false,
  String name = 'Personne partagée',
  String bio = 'Déclaration datée privée',
}) => ApiResponse(
  200,
  jsonEncode({
    'meta': {
      'projection': 'sharing.passport.document',
      'schema_version': 1,
      'generated_at': '2026-11-02T10:00:00Z',
      'scope': 'reader',
    },
    'data': {
      'document_id': 'PM-P-20261102-AAAA1111',
      'public_identifier': 'profil-lecteur',
      'subject_kind': 'profile',
      'variant': explicit ? 'custom' : 'complete',
      'issued_at': '2026-11-02T09:00:00Z',
      'expires_at': explicit ? '2026-11-30T10:00:00Z' : null,
      'revoked': revoked,
      'integrity_ok': true,
      'can_view_content': readable,
      'explicit_share': explicit,
      'payload': readable
          ? {
              'identity': {
                'name': name,
                'bio': bio,
                'profession': '',
                'links': const [],
                'owner_details': const {},
              },
              'interests': ['Bénévolat'],
              'open_to': const [],
              'activities': const [],
              'proofs': const [],
              'credentials': const [],
            }
          : null,
    },
  }),
  const {},
);

class _ReaderApi implements MakoloApiClient {
  _ReaderApi(this.next);

  Future<ApiResponse> Function(String path) next;
  String? requestedPath;
  bool usedPublicReader = false;

  @override
  Uri get baseUri => Uri.parse('https://example.test/');

  @override
  Future<ApiResponse> publicGet(
    String path, {
    Map<String, String>? headers,
    MakoloCancelHandle? cancel,
  }) async {
    requestedPath = path;
    usedPublicReader = true;
    return next(path);
  }

  @override
  Future<ApiResponse> get(
    String path, {
    Map<String, String>? headers,
    MakoloCancelHandle? cancel,
  }) async {
    requestedPath = path;
    usedPublicReader = false;
    return next(path);
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class _ReaderRuntime extends Fake implements AppRuntime {
  _ReaderRuntime(this.client) : authenticated = false;

  final _ReaderApi client;
  final bool authenticated;

  @override
  MakoloApiClient? get api => client;

  @override
  bool get isAuthenticated => authenticated;
}

void main() {
  test('structured Passport links remain public reader routes', () {
    const resolver = DeepLinkResolver();
    expect(
      resolver.resolve(
        const StructuredDestination(kind: 'passport_shared', id: 'opaque-link'),
      ),
      '/passport/shared/opaque-link',
    );
    expect(
      resolver.resolve(
        const StructuredDestination(
          kind: 'passport_verify',
          id: 'signed:document',
        ),
      ),
      '/passport/verify/signed%3Adocument',
    );
  });

  testWidgets('signed verification does not reveal a private issued Passport', (
    tester,
  ) async {
    final client = _ReaderApi(
      (_) async => _documentEnvelope(explicit: false, readable: false),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: PassportDocumentReaderScreen(
          runtime: _ReaderRuntime(client),
          token: 'signed:token',
          explicitShare: false,
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(client.usedPublicReader, isTrue);
    expect(client.requestedPath, contains('passport/verify/'));
    expect(
      find.textContaining('Le contenu n’est pas disponible'),
      findsOneWidget,
    );
    expect(find.text('Déclaration datée privée'), findsNothing);
  });

  testWidgets(
    'explicit granted share is read natively without elevating identity',
    (tester) async {
      final client = _ReaderApi(
        (_) async => _documentEnvelope(explicit: true, readable: true),
      );
      await tester.pumpWidget(
        MaterialApp(
          home: PassportDocumentReaderScreen(
            runtime: _ReaderRuntime(client),
            token: 'granted',
            explicitShare: true,
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(client.usedPublicReader, isTrue);
      expect(find.text('Personne partagée'), findsOneWidget);
      expect(find.text('Déclaration datée privée'), findsOneWidget);
      expect(find.text('Bénévolat'), findsOneWidget);
      expect(find.textContaining('Partage volontaire'), findsOneWidget);
    },
  );

  testWidgets('an invalidated share never leaves previous content visible', (
    tester,
  ) async {
    final first = Completer<ApiResponse>();
    final client = _ReaderApi((path) {
      if (path.contains('/old/')) return first.future;
      return Future.error(StateError('Revoked'));
    });
    final runtime = _ReaderRuntime(client);
    await tester.pumpWidget(
      MaterialApp(
        home: PassportDocumentReaderScreen(
          runtime: runtime,
          token: 'old',
          explicitShare: true,
        ),
      ),
    );
    await tester.pump();
    await tester.pumpWidget(
      MaterialApp(
        home: PassportDocumentReaderScreen(
          runtime: runtime,
          token: 'new',
          explicitShare: true,
        ),
      ),
    );
    await tester.pumpAndSettle();
    first.complete(_documentEnvelope(explicit: true, readable: true));
    await tester.pumpAndSettle();
    expect(find.text('Personne partagée'), findsNothing);
    expect(find.textContaining('expiré, révoqué'), findsOneWidget);
  });
}
