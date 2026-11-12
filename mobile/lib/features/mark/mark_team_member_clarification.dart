import 'package:flutter/material.dart';

import '../../design/action_controls.dart';

/// Clarifies one owner-defined Space team action. The backend, not these
/// fields, decides whether the actor may manage this Space.
class MarkTeamMemberClarification extends StatefulWidget {
  const MarkTeamMemberClarification({
    super.key,
    required this.onSubmit,
  });

  final void Function(String email, String role) onSubmit;

  @override
  State<MarkTeamMemberClarification> createState() =>
      _MarkTeamMemberClarificationState();
}

class _MarkTeamMemberClarificationState
    extends State<MarkTeamMemberClarification> {
  final _email = TextEditingController();
  final _role = TextEditingController();

  @override
  void dispose() {
    _email.dispose();
    _role.dispose();
    super.dispose();
  }

  void _submit() {
    final email = _email.text.trim().toLowerCase();
    final role = _role.text.trim();
    if (email.isEmpty ||
        !email.contains('@') ||
        email.contains(' ') ||
        role.isEmpty ||
        email.length > 254 ||
        role.length > 120) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Vérifiez l’adresse e-mail et le rôle.'),
        ),
      );
      return;
    }
    widget.onSubmit(email, role);
  }

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      const SizedBox(height: 12),
      TextField(
        controller: _email,
        keyboardType: TextInputType.emailAddress,
        autofillHints: const [AutofillHints.email],
        textInputAction: TextInputAction.next,
        decoration: const InputDecoration(
          labelText: 'E-mail de la personne',
          prefixIcon: Icon(Icons.person_outline),
        ),
      ),
      const SizedBox(height: 8),
      TextField(
        controller: _role,
        maxLength: 120,
        textInputAction: TextInputAction.done,
        onSubmitted: (_) => _submit(),
        decoration: const InputDecoration(
          labelText: 'Rôle à attribuer',
          prefixIcon: Icon(Icons.badge_outlined),
        ),
      ),
      MakoloActionButton(
        label: 'Vérifier cette proposition',
        onPressed: _submit,
        icon: Icons.arrow_forward_outlined,
        appearance: MakoloActionAppearance.secondary,
      ),
    ],
  );
}
