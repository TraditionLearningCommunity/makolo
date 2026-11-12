import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:makolo_mobile/features/mark/mark_team_member_clarification.dart';

void main() {
  testWidgets('Space team details are explicit inputs, not implicit authority', (
    tester,
  ) async {
    String? email;
    String? role;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: MarkTeamMemberClarification(
            onSubmit: (address, selectedRole) {
              email = address;
              role = selectedRole;
            },
          ),
        ),
      ),
    );

    await tester.enterText(
      find.widgetWithText(TextField, 'E-mail de la personne'),
      '  EXAMPLE@TEST.LOCAL  ',
    );
    await tester.enterText(
      find.widgetWithText(TextField, 'Rôle à attribuer'),
      'organizer',
    );
    await tester.tap(find.text('Vérifier cette proposition'));
    await tester.pump();

    expect(email, 'example@test.local');
    expect(role, 'organizer');
  });
}
