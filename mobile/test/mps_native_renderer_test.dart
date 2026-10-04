import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/presentation/mps/mps_models.dart';
import 'package:makolo_mobile/presentation/mps/mps_native_renderer.dart';

void main() {
  MpsArtifact artifact({
    Set<String> capabilities = const {},
    Map<String, String> links = const {},
    int minimumRendererVersion = 1,
  }) => MpsArtifact(
    resourceKey: 'access:1:access_pass',
    purpose: 'access_pass',
    template: const MpsDefinitionRef(
      resourceKey: mpsEssentialTemplateResourceKey,
      builtin: true,
    ),
    theme: const MpsDefinitionRef(
      resourceKey: mpsEssentialThemeResourceKey,
      builtin: true,
    ),
    context: const {
      'activity': {'display_title': 'Formation Makolo'},
      'occurrence': {
        'starts_at': '2026-10-12T14:00:00+02:00',
        'place': 'Lubumbashi',
      },
      'access': {
        'display_type': 'Billet',
        'display_status': 'Valide',
        'beneficiary': 'Amina',
      },
      'editorial': {'intro': 'Bienvenue', 'footer_note': 'Makolo'},
    },
    capabilities: capabilities,
    links: links,
    rendererContract: 'mps.native.v1',
    minimumRendererVersion: minimumRendererVersion,
  );

  testWidgets(
    'renderer resolves MPS bindings from authorized context',
    (tester) async {
      final value = MpsPresentationPackage(
        artifact: artifact(),
        manifest: mpsEssentialManifest,
        themeTokens: mpsEssentialTheme,
        usedFallback: false,
      );
      await tester.pumpWidget(
        MaterialApp(home: Scaffold(body: MpsNativeRenderer(package: value))),
      );

      expect(find.text('Formation Makolo'), findsOneWidget);
      expect(find.text('Bienvenue'), findsOneWidget);
      expect(find.text('Billet'), findsOneWidget);
      expect(find.text('Amina'), findsOneWidget);
      expect(find.text('Valide'), findsOneWidget);
    },
  );

  testWidgets('QRCode remains a revalidated owner action', (tester) async {
    var opened = false;
    final value = MpsPresentationPackage(
      artifact: artifact(
        capabilities: const {'open_credential'},
        links: const {'credential': '/api/v1/me/accesses/1/credential/'},
      ),
      manifest: mpsEssentialManifest,
      themeTokens: mpsEssentialTheme,
      usedFallback: false,
    );
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: MpsNativeRenderer(
            package: value,
            onOpenCredential: () => opened = true,
          ),
        ),
      ),
    );

    expect(find.text('Afficher le QR'), findsOneWidget);
    await tester.tap(find.text('Afficher le QR'));
    expect(opened, isTrue);
  });

  testWidgets('future renderer versions degrade to Essential', (tester) async {
    final value = MpsPresentationPackage(
      artifact: artifact(minimumRendererVersion: 99),
      manifest: const {
        'layout': {
          'component': 'FutureComponent',
          'props': <String, dynamic>{},
        },
      },
      themeTokens: mpsEssentialTheme,
      usedFallback: false,
    );
    await tester.pumpWidget(
      MaterialApp(home: Scaffold(body: MpsNativeRenderer(package: value))),
    );
    expect(find.text('Formation Makolo'), findsOneWidget);
  });
}
