import 'dart:async';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../app/runtime/app_runtime.dart';

/// Funding owns contribution validation and its PaymentObligation.
/// This native view never constructs a financial obligation locally.
class FundingContributionScreen extends StatefulWidget {
  const FundingContributionScreen({
    super.key,
    required this.runtime,
    required this.fundingId,
  });

  final AppRuntime runtime;
  final String fundingId;

  @override
  State<FundingContributionScreen> createState() =>
      _FundingContributionScreenState();
}

class _FundingContributionScreenState extends State<FundingContributionScreen> {
  final TextEditingController _amount = TextEditingController();
  final String _reference = _newReference();

  Map<String, dynamic>? _funding;
  bool _loading = true;
  bool _submitting = false;
  String? _error;
  String? _obligationId;
  String? _attemptedAmount;

  static String _newReference() {
    final random = Random.secure();
    return List.generate(
      32,
      (_) => random.nextInt(16).toRadixString(16),
    ).join();
  }

  @override
  void initState() {
    super.initState();
    unawaited(_load());
  }

  @override
  void dispose() {
    _amount.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final api = widget.runtime.api;
      if (api == null) throw StateError('API unavailable');
      final id = Uri.encodeComponent(widget.fundingId);
      final response = await api.publicGet('api/v1/funding/public/$id/');
      final data = response.jsonObject();
      if (data['id'] != widget.fundingId) {
        throw const FormatException('Funding identity mismatch');
      }
      if (!mounted) return;
      setState(() {
        _funding = data;
        _loading = false;
      });
    } on Object {
      if (!mounted) return;
      setState(() {
        _error = 'Ce financement n’est pas disponible.';
        _loading = false;
      });
    }
  }

  Future<void> _contribute() async {
    if (_submitting || _funding?['accepts_contributions'] != true) return;
    if (!widget.runtime.isAuthenticated) {
      widget.runtime.recovery.requireAuthentication(
        '/funding/' + widget.fundingId + '/contribute',
      );
      context.push('/login');
      return;
    }
    final value = _amount.text.trim().replaceAll(',', '.');
    if (!RegExp(r'^\d+(\.\d{1,2})?$').hasMatch(value) ||
        (num.tryParse(value) ?? 0) <= 0) {
      setState(() => _error = 'Indiquez un montant valide.');
      return;
    }
    final minimum = num.tryParse(
      _funding?['minimum_contribution']?.toString() ?? '',
    );
    final maximum = num.tryParse(
      _funding?['maximum_contribution']?.toString() ?? '',
    );
    final amount = num.parse(value);
    if ((minimum != null && amount < minimum) ||
        (maximum != null && amount > maximum)) {
      setState(() => _error = 'Montant hors des limites du financement.');
      return;
    }
    if (_attemptedAmount != null && _attemptedAmount != value) {
      setState(() => _error = 'Réessayez avec le montant initial.');
      return;
    }
    setState(() {
      _attemptedAmount = value;
      _submitting = true;
      _error = null;
    });
    try {
      final id = Uri.encodeComponent(widget.fundingId);
      final response = await widget.runtime.api!.post(
        'api/v1/funding/$id/contributions/',
        body: {'amount': value, 'client_reference': _reference},
      );
      final data = response.jsonObject();
      final obligation = data['payment_obligation_id'];
      if (obligation is! String || obligation.isEmpty) {
        throw const FormatException('Obligation identity missing');
      }
      _obligationId = obligation;
      if (!mounted) return;
      context.push('/payments/obligations/' + Uri.encodeComponent(obligation));
    } on Object {
      if (!mounted) return;
      setState(() {
        _error = 'Contribution non confirmée. Réessayez sans changer le montant.';
      });
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final funding = _funding;
    return Scaffold(
      appBar: AppBar(title: const Text('Contribuer')),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          if (_loading)
            const Center(child: CircularProgressIndicator())
          else if (funding == null)
            OutlinedButton(
              onPressed: _load,
              child: const Text('Réessayer'),
            )
          else ...[
            Text(
              funding['title']?.toString() ?? 'Financement',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            if ((funding['description'] ?? '').toString().isNotEmpty) ...[
              const SizedBox(height: 12),
              Text(funding['description'].toString()),
            ],
            const SizedBox(height: 20),
            Text(
              'Réuni : ' +
                  (funding['raised_amount']?.toString() ?? '0') +
                  ' ' +
                  (funding['currency']?.toString() ?? ''),
            ),
            if (funding['target_amount'] != null)
              Text(
                'Objectif : ' +
                    funding['target_amount'].toString() +
                    ' ' +
                    (funding['currency']?.toString() ?? ''),
              ),
            const SizedBox(height: 20),
            if (funding['accepts_contributions'] == true) ...[
              TextField(
                controller: _amount,
                enabled: !_submitting &&
                    _obligationId == null &&
                    _attemptedAmount == null,
                keyboardType: const TextInputType.numberWithOptions(
                  decimal: true,
                ),
                decoration: InputDecoration(
                  labelText: 'Montant (' +
                      (funding['currency']?.toString() ?? '') +
                      ')',
                  helperText: _limitLabel(funding),
                ),
              ),
              const SizedBox(height: 20),
              FilledButton.icon(
                onPressed: _submitting || _obligationId != null
                    ? null
                    : _contribute,
                icon: const Icon(Icons.volunteer_activism_outlined),
                label: Text(
                  _submitting
                      ? 'Contribution en cours…'
                      : widget.runtime.isAuthenticated
                          ? 'Continuer vers le paiement'
                          : 'Se connecter pour contribuer',
                ),
              ),
              if (_obligationId case final id?) ...[
                const SizedBox(height: 12),
                OutlinedButton(
                  onPressed: () => context.push(
                    '/payments/obligations/' + Uri.encodeComponent(id),
                  ),
                  child: const Text('Voir mon paiement'),
                ),
              ],
            ] else
              const Text('Ce financement n’accepte plus de contributions.'),
          ],
          if (_error case final error?) ...[
            const SizedBox(height: 12),
            Text(
              error,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          ],
        ],
      ),
    );
  }

  String? _limitLabel(Map<String, dynamic> data) {
    final minimum = data['minimum_contribution'];
    final maximum = data['maximum_contribution'];
    if (minimum == null && maximum == null) return null;
    if (minimum != null && maximum != null) {
      return 'De ' + minimum.toString() + ' à ' + maximum.toString();
    }
    return minimum != null
        ? 'Minimum : ' + minimum.toString()
        : 'Maximum : ' + maximum.toString();
  }
}
