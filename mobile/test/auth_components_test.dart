import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/design/makolo_theme.dart';
import 'package:makolo_mobile/design/makolo_mark.dart';
import 'package:makolo_mobile/features/auth/auth_components.dart';
import 'package:makolo_mobile/features/auth/auth_entry_frame.dart';

void main() {
  for (final dark in [false, true]) {
    testWidgets(
      'violet Auth labels and field semantics in ${dark ? "dark" : "light"} mode',
      (tester) async {
        final semantics = tester.ensureSemantics();

        await tester.pumpWidget(
          MaterialApp(
            theme: dark ? buildMakoloDarkTheme() : buildMakoloLightTheme(),
            home: const AuthEntryFrame(
              title: 'Connexion',
              child: MakoloAuthField(
                label: 'Identifiant Makolo',
                hint: 'Votre identifiant',
                fieldKey: Key('identifier'),
                textInputAction: TextInputAction.next,
                autofillHints: [AutofillHints.username],
              ),
            ),
          ),
        );
        final field = tester.widget<TextFormField>(
          find.byKey(const Key('identifier')),
        );
        final input = tester.widget<TextField>(
          find.descendant(
            of: find.byKey(const Key('identifier')),
            matching: find.byType(TextField),
          ),
        );
        expect(field.enabled, isTrue);
        expect(input.decoration!.labelText, isNull);
        expect((input.decoration!.hint! as Text).data, 'Votre identifiant');
        expect(
          tester.getBottomLeft(find.text('Identifiant Makolo')).dy,
          lessThan(tester.getTopLeft(find.byKey(const Key('identifier'))).dy),
        );
        expect(input.decoration!.fillColor, MakoloColors.warm);
        expect(input.style!.color, MakoloColors.ink);
        expect(
          tester.widget<Scaffold>(find.byType(Scaffold)).backgroundColor,
          MakoloColors.indigo,
        );
        expect(input.autofillHints, [AutofillHints.username]);
        expect(input.textInputAction, TextInputAction.next);
        expect(
          tester.widget<Text>(find.text('Identifiant Makolo')).style!.color,
          Colors.white,
        );
        expect(
          tester.widget<MakoloMark>(find.byType(MakoloMark)).white,
          isTrue,
        );
        expect(find.byType(Card), findsNothing);
        expect(
          find.bySemanticsLabel(
            RegExp('Identifiant Makolo.*Votre identifiant', dotAll: true),
          ),
          findsOneWidget,
        );
        await tester.enterText(find.byKey(const Key('identifier')), '@amina');
        expect(
          tester.getSemantics(find.byType(EditableText)).label,
          contains('Identifiant Makolo'),
        );
        expect(tester.takeException(), isNull);
        semantics.dispose();
      },
    );
  }

  testWidgets('busy primary action exposes progress and blocks duplicates', (
    tester,
  ) async {
    var calls = 0;
    final semantics = tester.ensureSemantics();

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: MakoloAuthPrimaryButton(
            label: 'Se connecter',
            busy: true,
            onPressed: () => calls++,
          ),
        ),
      ),
    );
    expect(
      tester.widget<FilledButton>(find.byType(FilledButton)).onPressed,
      isNull,
    );
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
    expect(find.bySemanticsLabel('Traitement en cours'), findsOneWidget);
    await tester.tap(find.byType(FilledButton));
    expect(calls, 0);
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: MakoloAuthPrimaryButton(
            label: 'Se connecter',
            onPressed: () => calls++,
          ),
        ),
      ),
    );
    await tester.tap(find.text('Se connecter'));
    expect(calls, 1);
    final style = tester.widget<FilledButton>(find.byType(FilledButton)).style!;
    expect(style.backgroundColor!.resolve({}), Colors.white);
    expect(style.foregroundColor!.resolve({}), MakoloColors.deep);
    semantics.dispose();
  });

  testWidgets('Auth placeholders wrap without truncation on a small screen', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(320, 568);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(
      MaterialApp(
        theme: buildMakoloDarkTheme(),
        home: MediaQuery(
          data: const MediaQueryData(
            size: Size(320, 568),
            textScaler: TextScaler.linear(2),
          ),
          child: const AuthEntryFrame(
            title: 'Connexion',
            child: MakoloAuthField(
              label: 'Confirmer le mot de passe',
              hint: 'Répétez le mot de passe',
              prefixIcon: Icons.lock_outline,
              suffixIcon: Icon(Icons.visibility),
            ),
          ),
        ),
      ),
    );
    final paragraph = tester.renderObject<RenderParagraph>(
      find.text('Répétez le mot de passe'),
    );
    expect(paragraph.didExceedMaxLines, isFalse);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'frame scrolls with keyboard and large text and keeps back usable',
    (tester) async {
      tester.view.physicalSize = const Size(320, 568);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      var backs = 0;
      await tester.pumpWidget(
        MaterialApp(
          home: MediaQuery(
            data: const MediaQueryData(
              size: Size(320, 568),
              viewInsets: EdgeInsets.only(bottom: 280),
              textScaler: TextScaler.linear(2),
            ),
            child: AuthEntryFrame(
              title: 'Créer un compte',
              footer: 'Pied de page',
              onBack: () => backs++,
              child: Column(
                children: [
                  for (var i = 0; i < 7; i++)
                    const MakoloAuthField(
                      label: 'Identifiant Makolo',
                      hint: 'Votre identifiant',
                    ),
                  MakoloAuthPrimaryButton(
                    label: 'Créer mon compte',
                    onPressed: () {},
                  ),
                ],
              ),
            ),
          ),
        ),
      );
      expect(find.text('Pied de page'), findsNothing);
      expect(
        tester
            .widget<SingleChildScrollView>(find.byType(SingleChildScrollView))
            .keyboardDismissBehavior,
        ScrollViewKeyboardDismissBehavior.onDrag,
      );
      await tester.ensureVisible(find.text('Créer mon compte'));
      await tester.pumpAndSettle();
      expect(
        tester.getBottomLeft(find.text('Créer mon compte')).dy,
        lessThan(288),
      );
      await tester.ensureVisible(find.byTooltip('Retour'));
      await tester.tap(find.byTooltip('Retour'));
      expect(backs, 1);
      expect(tester.takeException(), isNull);
    },
  );
}
