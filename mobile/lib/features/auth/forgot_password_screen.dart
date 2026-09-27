import 'package:flutter/material.dart';

import '../../app/providers.dart';
import '../../auth/auth_repository.dart';
import '../../design/makolo_theme.dart';
import 'auth_entry_frame.dart';
import 'auth_error_messages.dart';

class ForgotPasswordScreen extends StatefulWidget {
  const ForgotPasswordScreen({
    super.key,
    required this.runtime,
    required this.onBackToLogin,
    this.initialEmail = '',
  });

  final AppRuntime runtime;
  final ValueChanged<String> onBackToLogin;
  final String initialEmail;

  @override
  State<ForgotPasswordScreen> createState() => _ForgotPasswordScreenState();
}

class _ForgotPasswordScreenState extends State<ForgotPasswordScreen> {
  late final TextEditingController _email;
  bool _busy = false;
  String? _error;
  bool _sent = false;

  @override
  void initState() {
    super.initState();
    _email = TextEditingController(text: widget.initialEmail);
  }

  @override
  void dispose() {
    _email.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_busy) return;
    final email = _email.text.trim();
    if (email.isEmpty || !email.contains('@')) {
      setState(() {
        _error = 'Indiquez une adresse e-mail valide.';
        _sent = false;
      });
      return;
    }
    final api = widget.runtime.api;
    if (api == null) {
      setState(() {
        _error = 'La récupération est indisponible sur cette installation pour le moment.';
        _sent = false;
      });
      return;
    }

    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await AuthRepository(
        api,
        widget.runtime.tokens,
      ).forgotPassword(email: email);
      if (!mounted) return;
      setState(() => _sent = true);
    } on Object catch (error) {
      if (!mounted) return;
      setState(() {
        _error = authErrorMessage(
          error,
          fallback:
              'Envoi impossible pour le moment. Réessayez dans un instant.',
        );
        _sent = false;
      });
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return AuthEntryFrame(
      title: 'Mot de passe oublié ?',
      subtitle: 'Si un compte correspond à cette adresse, Makolo envoie les instructions de réinitialisation.',
      onBack: () => widget.onBackToLogin(_email.text.trim()),
      child: AutofillGroup(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            TextField(
              key: const Key('forgot-email'),
              controller: _email,
              enabled: !_busy,
              keyboardType: TextInputType.emailAddress,
              autofillHints: const [AutofillHints.email],
              textInputAction: TextInputAction.done,
              onSubmitted: (_) => _submit(),
              decoration: const InputDecoration(
                labelText: 'Adresse e-mail',
                border: OutlineInputBorder(),
              ),
            ),
            if (_error != null) ...[
              const SizedBox(height: MakoloSpacing.md),
              Semantics(
                liveRegion: true,
                child: Text(
                  _error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ),
            ],
            if (_sent) ...[
              const SizedBox(height: MakoloSpacing.md),
              Semantics(
                liveRegion: true,
                child: const Text(
                  'Si un compte correspond à cette adresse, les instructions ont été envoyées. Ouvrez le lien reçu pour terminer la réinitialisation sur le web, puis revenez vous connecter dans Makolo.',
                ),
              ),
            ],
            const SizedBox(height: MakoloSpacing.lg),
            FilledButton(
              key: const Key('forgot-submit'),
              onPressed: _busy ? null : _submit,
              child: Text(_busy ? 'Envoi…' : 'Envoyer les instructions'),
            ),
            const SizedBox(height: MakoloSpacing.sm),
            TextButton(
              onPressed: _busy
                  ? null
                  : () => widget.onBackToLogin(_email.text.trim()),
              child: const Text('Retour à la connexion'),
            ),
          ],
        ),
      ),
    );
  }
}
