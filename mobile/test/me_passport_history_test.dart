import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/me/me_passport_screen.dart';
import 'package:makolo_mobile/network/makolo_api_client.dart';

const _versionId = '11111111-1111-4111-8111-111111111111';
const _shareId = '22222222-2222-4222-8222-222222222222';

class _DatedPassportApi implements MakoloApiClient {
  _DatedPassportApi({this.withShares = false});
  final bool withShares;
  bool revoked = false;
  bool shareRevoked = false;
  String? lastPostPath;
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
            'revoked': revoked,
            'active_shares': withShares && !shareRevoked && !revoked
                ? [
                    {'id': _shareId, 'expires_at': '2026-11-30T10:00:00Z'},
                  ]
                : const [],
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
  Future<ApiResponse> post(
    String path, {
    Map<String, dynamic>? body,
    Map<String, String>? headers,
    MakoloCancelHandle? cancel,
  }) async {
    lastPostPath = path;
    if (path.contains('passport/history/$_versionId/revoke/')) {
      revoked = true;
      return _envelope('personal.me.passport.version', {
        'id': _versionId,
        'revoked': true,
      });
    }
    if (path.contains('passport/shares/$_shareId/revoke/')) {
      shareRevoked = true;
      return _envelope('personal.me.passport.share', {
        'share_id': _shareId,
        'revoked': true,
      });
    }
    throw StateError('Unexpected post: $path');
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class _DelayedVariantApi extends _DatedPassportApi {
  final publicResult = Completer<ApiResponse>();

  @override
  Future<ApiResponse> get(
    String path, {
    Map<String, String>? headers,
    MakoloCancelHandle? cancel,
  }) {
    if (Uri.parse(path).queryParameters['variant'] == 'public') {
      return publicResult.future;
    }
    return super.get(path, headers: headers, cancel: cancel);
  }
}

class _UnavailablePassportApi implements MakoloApiClient {
  @override
  Uri get baseUri => Uri.parse('https://example.test/');

  @override
  Future<ApiResponse> get(
    String path, {
    Map<String, String>? headers,
    MakoloCancelHandle? cancel,
  }) async => throw StateError('Offline');

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
      await tester.tap(find.byTooltip('Autres actions du Passeport'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Versions datées'));
      await tester.pumpAndSettle();
      expect(find.text('PM-P-20261030-11111111'), findsOneWidget);
      await tester.tap(find.text('PM-P-20261030-11111111'));
      await tester.pumpAndSettle();
      expect(find.text('Présentation telle qu’émise.'), findsOneWidget);
      expect(find.text('Recherche'), findsOneWidget);
    },
  );
  testWidgets('native owner can revoke an issued version and refresh history', (tester) async {
    final api = _DatedPassportApi();
    await tester.pumpWidget(MaterialApp(home: MePassportScreen(api: api)));
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip('Autres actions du Passeport'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Versions datées'));
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('Gérer cette version'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Révoquer cette version'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Révoquer la version'));
    await tester.pumpAndSettle();

    expect(api.lastPostPath, 'api/v1/me/passport/history/$_versionId/revoke/');
    expect(api.revoked, isTrue);
    expect(find.textContaining('Révoqué'), findsWidgets);
  });

  testWidgets('native owner can revoke one share without revoking the version', (tester) async {
    final api = _DatedPassportApi(withShares: true);
    await tester.pumpWidget(MaterialApp(home: MePassportScreen(api: api)));
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip('Autres actions du Passeport'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Versions datées'));
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('Gérer cette version'));
    await tester.pumpAndSettle();
    await tester.tap(find.textContaining('Révoquer le lien ·'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Révoquer le lien'));
    await tester.pumpAndSettle();

    expect(api.lastPostPath, 'api/v1/me/passport/shares/$_shareId/revoke/');
    expect(api.shareRevoked, isTrue);
    expect(api.revoked, isFalse);
  });

  testWidgets('network error is recoverable and variant controls remain available', (tester) async {
    await tester.pumpWidget(
      MaterialApp(home: MePassportScreen(api: _UnavailablePassportApi())),
    );
    await tester.pumpAndSettle();

    expect(find.textContaining('Passeport indisponible'), findsOneWidget);
    expect(find.text('Réessayer'), findsOneWidget);
    expect(find.text('Public'), findsOneWidget);
    await tester.tap(find.text('Réessayer'));
    await tester.pumpAndSettle();
    expect(find.text('Réessayer'), findsOneWidget);
  });

  testWidgets('switching Passport variant never paints previous private data', (tester) async {
    final api = _DelayedVariantApi();
    await tester.pumpWidget(MaterialApp(home: MePassportScreen(api: api)));
    await tester.pumpAndSettle();
    expect(find.text('Présentation actuellement mise à jour.'), findsOneWidget);

    await tester.tap(find.text('Public'));
    await tester.pump();
    expect(find.text('Présentation actuellement mise à jour.'), findsNothing);

    api.publicResult.complete(api._envelope('personal.me.passport', {
      'variant': 'public',
      'identity': {'name': 'Profil public', 'links': const []},
      'declared': {'interests': const [], 'open_to': const []},
      'activities': const [],
      'established': {'proofs': const []},
      'issued': {'credentials': const []},
    }));
    await tester.pumpAndSettle();
    expect(find.text('Profil public'), findsOneWidget);
    expect(find.text('Présentation actuellement mise à jour.'), findsNothing);
  });

}
