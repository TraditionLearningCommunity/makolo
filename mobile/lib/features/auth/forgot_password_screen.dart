import 'package:flutter/material.dart';

import '../../app/providers.dart';
import '../../auth/auth_repository.dart';
import '../../design/makolo_theme.dart';
import 'auth_error_messages.dart';

Future<String?> showForgotPasswordDialog(
  BuildContext context, {
  required AppRuntime runtime,
  String initialEmail = '',
}) {
  return showDialog<String>(
    context: context,
    builder: (_) => _ForgotPasswordDialog(
      runtime: runtime,
      initialEmail: initialEmail,
    ),
  );
}

class _ForgotPasswordDialog extends StatefulWidget {
  const _ForgotPasswordDialog({
    required this.runtime,
    required this.initialEmail,
  });

  final AppRuntime runtime;
  final String initialEmail;

  @override
  State<_ForgotPasswordDialog> createState() =>
      _ForgotPasswordDialogState();
}

class _ForgotPasswordDialogState extends State<_ForgotPasswordDialog> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _email;
  bool _busy = false;
  bool _sent = false;
  String? _error;

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

  String? _validateEmail(String? value) {
    final email = value?.trim() ?? '';
    if (email.isEmpty || !email.contains('@')) {
      return 'Indiquez une adresse e-mail valide.';
    }
    return null;
  }

  Future<void> _submit() async {
    if (_busy || !_formKey.currentState!.validate()) return;
    final api = widget.runtime.api;
    if (api == null) {
      setState(() {
        _error =
            'La récupération est indisponible sur cette installation pour le moment.';
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
      ).forgotPassword(email: _email.text.trim());
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
      });
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      backgroundColor: MakoloColors.warm,
      surfaceTintColor: Colors.transparent,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(MakoloRadii.large),
      ),
      title: Text(
        _sent ? 'Consultez votre boîte de réception' : 'Mot de passe oublié ?',
      ),
      content: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 420),
        child: _sent
            ? Semantics(
                liveRegion: true,
                child: Text(
                  'Si un compte correspond à ${_email.text.trim()}, Makolo y a envoyé les instructions. Ouvrez le lien reçu pour réinitialiser votre mot de passe, puis revenez vous connecter.',
                  style: const TextStyle(height: 1.45),
                ),
              )
            : Form(
                key: _formKey,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Text(
                      'Indiquez l’adresse e-mail de votre compte. Makolo répond de la même façon qu’un compte existe ou non.',
                    ),
                    const SizedBox(height: MakoloSpacing.lg),
                    TextFormField(
                      key: const Key('forgot-email'),
                      controller: _email,
                      enabled: !_busy,
                      keyboardType: TextInputType.emailAddress,
                      autofillHints: const [AutofillHints.email],
                      textInputAction: TextInputAction.done,
                      validator: _validateEmail,
                      onFieldSubmitted: (_) => _submit(),
                      decoration: InputDecoration(
                        labelText: 'Adresse e-mail',
                        prefixIcon: const Icon(Icons.alternate_email),
                        filled: true,
                        fillColor: Colors.white,
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(16),
                        ),
                      ),
                    ),
                    if (_error != null) ...[
                      const SizedBox(height: MakoloSpacing.md),
                      Semantics(
                        liveRegion: true,
                        child: Text(
                          _error!,
                          style: TextStyle(
                            color: Theme.of(context).colorScheme.error,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ],
                  ],
                ),
              ),
      ),
      actions: [
        TextButton(
          onPressed: _busy
              ? null
              : () => Navigator.of(context).pop(_email.text.trim()),
          child: Text(_sent ? 'Fermer' : 'Annuler'),
        ),
        if (!_sent)
          FilledButton(
            key: const Key('forgot-submit'),
            onPressed: _busy ? null : _submit,
            child: Text(_busy ? 'Envoi…' : 'Envoyer'),
          ),
      ],
    );
  }
}
