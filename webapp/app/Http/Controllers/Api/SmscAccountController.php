<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\DB;

/**
 * Internal API consumed only by the chatbot-ai backend's SMSC integration
 * (see chatbot-ai/backend/app/core/smsc_client.py for the exact contract).
 * Never exposed to the public widget — every route here sits behind
 * SmscApiAuth and the chatbot only calls it for a visitor who already
 * passed username validation in this same request chain.
 */
class SmscAccountController extends Controller
{
    public function validateUser(Request $request): JsonResponse
    {
        $request->validate(['username' => 'required|string']);

        $user = DB::table('users')
            ->where('username', $request->input('username'))
            ->where('status', 'active')
            ->first();

        if (! $user) {
            return response()->json(['success' => false]);
        }

        return response()->json([
            'success' => true,
            'user' => [
                'id' => $user->id,
                'username' => $user->username,
                'role' => $user->role,
            ],
        ]);
    }

    /**
     * Exchanges a short-lived, single-use token (minted by the Laravel
     * dashboard for its currently logged-in user, see resources/views/
     * dashboard.blade.php) for that user's SMSC identity. Lets the chatbot
     * widget greet an already-logged-in visitor by name without asking them
     * to retype their username. The token is pulled (read+delete) from
     * cache so it can never be replayed.
     */
    public function exchangeWidgetToken(Request $request): JsonResponse
    {
        $request->validate(['token' => 'required|string']);

        $userId = Cache::pull('widget_login_token:'.$request->input('token'));

        if (! $userId) {
            return response()->json(['success' => false]);
        }

        $user = DB::table('users')
            ->where('id', $userId)
            ->where('status', 'active')
            ->first();

        if (! $user) {
            return response()->json(['success' => false]);
        }

        return response()->json([
            'success' => true,
            'user' => [
                'id' => $user->id,
                'username' => $user->username,
                'role' => $user->role,
            ],
        ]);
    }

    public function balance(int $id): JsonResponse
    {
        $user = $this->activeUserOrFail($id);
        $account = DB::table('accounts')->where('id', $user->account_id)->first();
        $balance = $account ? DB::table('balances')->where('account_id', $account->id)->first() : null;

        if (! $account || ! $balance) {
            return response()->json(['error' => 'No account/balance on file'], 404);
        }

        return response()->json([
            'balance' => (float) $balance->current_balance,
            'reserved_balance' => (float) $balance->reserved_balance,
            'available_balance' => (float) $balance->current_balance - (float) $balance->reserved_balance,
            'currency' => $balance->currency,
            'low_balance_threshold' => (float) $balance->low_balance_threshold,
            'account_number' => $account->account_number,
            'account_name' => $account->account_name,
            'billing_type' => $account->billing_type,
        ]);
    }

    public function status(int $id): JsonResponse
    {
        $user = $this->activeUserOrFail($id);
        $account = DB::table('accounts')->where('id', $user->account_id)->first();
        $services = $this->servicesFor($id);

        return response()->json([
            'username' => $user->username,
            'email' => $user->email,
            'role' => $user->role,
            'status' => $user->status,
            'account_number' => $account->account_number ?? null,
            'account_name' => $account->account_name ?? null,
            'billing_type' => $account->billing_type ?? null,
            'sms_enabled' => (bool) $user->sms_enabled,
            'smpp_enabled' => (bool) ($services['smpp']->enabled ?? false),
            'http_api_enabled' => (bool) ($services['api']->enabled ?? false),
            'hlr_enabled' => (bool) ($services['hlr']->enabled ?? false),
            'dlr_enabled' => (bool) $user->dlr_enabled,
            'last_login_at' => $user->last_login_at,
        ]);
    }

    public function smppStatus(int $id): JsonResponse
    {
        $this->activeUserOrFail($id);
        $service = $this->serviceFor($id, 'smpp');
        $smpp = DB::table('smpp_configurations')->where('user_id', $id)->first();

        if (! $smpp) {
            return response()->json(['enabled' => (bool) ($service->enabled ?? false), 'tps' => $service->tps ?? null, 'configured' => false]);
        }

        return response()->json([
            'enabled' => (bool) ($service->enabled ?? false),
            'tps' => $service->tps ?? null,
            'configured' => true,
            'status' => $smpp->status,
            'host' => $smpp->host,
            'port' => $smpp->port,
            'system_id' => $smpp->system_id,
            'bind_type' => $smpp->bind_type,
            'tls_enabled' => (bool) $smpp->tls_enabled,
            'allowed_ips' => $this->allowedIpsFor($smpp->id),
        ]);
    }

    /**
     * @return array<int, array{ip_address: string, enabled: bool}>
     */
    private function allowedIpsFor(int $smppConfigurationId): array
    {
        return DB::table('smpp_allowed_ips')
            ->where('smpp_configuration_id', $smppConfigurationId)
            ->orderBy('ip_address')
            ->get()
            ->map(fn ($row) => ['ip_address' => $row->ip_address, 'enabled' => (bool) $row->enabled])
            ->all();
    }

    public function httpApiStatus(int $id): JsonResponse
    {
        $this->activeUserOrFail($id);
        $service = $this->serviceFor($id, 'api');
        $httpApi = DB::table('http_api_configurations')->where('user_id', $id)->first();

        if (! $httpApi) {
            return response()->json(['enabled' => (bool) ($service->enabled ?? false), 'tps' => $service->tps ?? null, 'configured' => false]);
        }

        return response()->json([
            'enabled' => (bool) ($service->enabled ?? false),
            'tps' => $service->tps ?? null,
            'configured' => true,
            'status' => $httpApi->status,
            'callback_url' => $httpApi->callback_url,
            'authentication_type' => $httpApi->authentication_type,
        ]);
    }

    public function hlrStatus(int $id): JsonResponse
    {
        $this->activeUserOrFail($id);
        $service = $this->serviceFor($id, 'hlr');

        return response()->json(['enabled' => (bool) ($service->enabled ?? false), 'tps' => $service->tps ?? null]);
    }

    private function serviceFor(int $userId, string $service): ?object
    {
        return DB::table('user_services')
            ->where('user_id', $userId)
            ->where('service', $service)
            ->first();
    }

    /**
     * @return array<string, object>
     */
    private function servicesFor(int $userId): array
    {
        return DB::table('user_services')
            ->where('user_id', $userId)
            ->get()
            ->keyBy('service')
            ->all();
    }

    public function dlrStatus(int $id): JsonResponse
    {
        $user = $this->activeUserOrFail($id);

        return response()->json(['enabled' => (bool) $user->dlr_enabled]);
    }

    public function connections(int $id): JsonResponse
    {
        $this->activeUserOrFail($id);

        $connections = [];

        $smpp = DB::table('smpp_configurations')->where('user_id', $id)->first();
        if ($smpp) {
            $connections[] = [
                'type' => 'smpp',
                'host' => $smpp->host,
                'port' => $smpp->port,
                'status' => $smpp->status,
                'tls_enabled' => (bool) $smpp->tls_enabled,
                'allowed_ips' => $this->allowedIpsFor($smpp->id),
            ];
        }

        $httpApi = DB::table('http_api_configurations')->where('user_id', $id)->first();
        if ($httpApi) {
            $connections[] = [
                'type' => 'http_api',
                'callback_url' => $httpApi->callback_url,
                'status' => $httpApi->status,
            ];
        }

        return response()->json(['connections' => $connections]);
    }

    public function traffic(int $id, Request $request): JsonResponse
    {
        $this->activeUserOrFail($id);

        [$dateFrom, $dateTo] = $this->resolveDateRange($request);

        $totals = DB::table('sms_usage')
            ->where('user_id', $id)
            ->whereBetween('usage_date', [$dateFrom, $dateTo])
            ->selectRaw('
                COALESCE(SUM(total_submitted), 0) as total_submitted,
                COALESCE(SUM(total_sent), 0) as total_sent,
                COALESCE(SUM(total_delivered), 0) as total_delivered,
                COALESCE(SUM(total_failed), 0) as total_failed,
                COALESCE(SUM(total_parts), 0) as total_parts,
                COALESCE(SUM(total_cost), 0) as total_cost
            ')
            ->first();

        return response()->json([
            'date_from' => $dateFrom,
            'date_to' => $dateTo,
            'total_submitted' => (int) $totals->total_submitted,
            'total_sent' => (int) $totals->total_sent,
            'total_delivered' => (int) $totals->total_delivered,
            'total_failed' => (int) $totals->total_failed,
            'total_parts' => (int) $totals->total_parts,
            'total_cost' => (float) $totals->total_cost,
        ]);
    }

    public function deliveryStats(int $id, Request $request): JsonResponse
    {
        $this->activeUserOrFail($id);

        [$dateFrom, $dateTo] = $this->resolveDateRange($request);

        $totals = DB::table('sms_usage')
            ->where('user_id', $id)
            ->whereBetween('usage_date', [$dateFrom, $dateTo])
            ->selectRaw('
                COALESCE(SUM(total_sent), 0) as total_sent,
                COALESCE(SUM(total_delivered), 0) as total_delivered,
                COALESCE(SUM(total_failed), 0) as total_failed
            ')
            ->first();

        $sent = (int) $totals->total_sent;
        $delivered = (int) $totals->total_delivered;
        $failed = (int) $totals->total_failed;
        $deliveryRate = $sent > 0 ? round(($delivered / $sent) * 100, 2) : null;

        return response()->json([
            'date_from' => $dateFrom,
            'date_to' => $dateTo,
            'sent' => $sent,
            'delivered' => $delivered,
            'failed' => $failed,
            'delivery_rate_percent' => $deliveryRate,
        ]);
    }

    /**
     * Platform-wide route pricing, not user-scoped (the price per country
     * is the same for every account — there is no per-customer pricing in
     * this demo). Exists so the AI can compute "can I afford to send N
     * messages" itself from balance + this list instead of asking the
     * visitor to go look up pricing somewhere, or inventing a number.
     */
    public function pricing(Request $request): JsonResponse
    {
        $serviceType = $request->query('service_type', 'sms_mt');
        abort_unless(in_array($serviceType, ['sms_mt', 'sms_mo', 'hlr'], true), 422, 'Invalid service_type.');

        $rows = DB::table('pricing')
            ->join('countries', 'countries.id', '=', 'pricing.country_id')
            ->where('pricing.service_type', $serviceType)
            ->where('pricing.status', 'active')
            ->whereNull('pricing.operator_id')
            ->whereDate('pricing.effective_from', '<=', now())
            ->where(function ($q) {
                $q->whereNull('pricing.effective_to')->orWhereDate('pricing.effective_to', '>=', now());
            })
            ->orderBy('countries.country_name')
            ->get(['countries.country_name', 'countries.iso_code', 'pricing.price', 'pricing.currency']);

        return response()->json([
            'service_type' => $serviceType,
            'rates' => $rows->map(fn ($r) => [
                'country' => $r->country_name,
                'iso_code' => $r->iso_code,
                'price_per_message' => (float) $r->price,
                'currency' => $r->currency,
            ]),
        ]);
    }

    /**
     * Platform-wide SMS package tiers, not user-scoped — same tiers for
     * every prospect. The public sales chatbot recommends the one whose
     * volume range covers the visitor's stated monthly volume; it never
     * invents a price, so price_amount comes through as null until this
     * table is given real numbers (see the 2026_09_08_120000 migration).
     */
    public function packages(): JsonResponse
    {
        $rows = DB::table('sms_packages')
            ->where('status', 'active')
            ->orderBy('display_order')
            ->get(['slug', 'name', 'min_monthly_volume', 'max_monthly_volume', 'price_amount', 'currency', 'billing_period', 'coverage_notes', 'features']);

        return response()->json([
            'packages' => $rows->map(fn ($r) => [
                'slug' => $r->slug,
                'name' => $r->name,
                'min_monthly_volume' => (int) $r->min_monthly_volume,
                'max_monthly_volume' => $r->max_monthly_volume === null ? null : (int) $r->max_monthly_volume,
                'price_amount' => $r->price_amount === null ? null : (float) $r->price_amount,
                'currency' => $r->currency,
                'billing_period' => $r->billing_period,
                'coverage_notes' => $r->coverage_notes,
                'features' => $r->features ? json_decode($r->features) : [],
            ]),
        ]);
    }

    /**
     * Support-only diagnostic lookup: "why wasn't message X sent". Not
     * user-scoped like the endpoints above — a support agent investigates
     * messages belonging to any user, identified only by the message id/
     * uuid they were given, never by picking a user. The chatbot only
     * offers this as a tool to sessions authenticated with role=support
     * (see smsc_ai_service._TOOLS_BY_ROLE); this endpoint itself trusts
     * the same internal bearer token as every other route here.
     */
    public function messageStatus(string $message): JsonResponse
    {
        $query = DB::table('messages')->where('message_uuid', $message);

        if (ctype_digit($message)) {
            $query->orWhere('id', (int) $message);
        }

        $row = $query->first();

        abort_unless($row, 404, 'No message found with that id.');

        $owner = DB::table('users')->where('id', $row->user_id)->value('username');

        return response()->json([
            'message_id' => $row->message_uuid,
            'username' => $owner,
            'service' => $row->service,
            'sender_id' => $row->sender_id_value,
            'destination' => $row->destination_number,
            'country' => $row->destination_country_code,
            'status' => $row->status,
            'is_sent' => (bool) $row->is_sent,
            'reason' => $row->response ?? $row->error_message,
            'submitted_at' => $row->submitted_at,
            'sent_at' => $row->sent_at,
            'delivered_at' => $row->delivered_at,
        ]);
    }

    /**
     * User-scoped counterpart to messageStatus() above: a regular customer
     * asking about their own message. Unlike the support-only lookup, this
     * filters by user_id as well as the message id/uuid, so a customer can
     * never see another customer's message this way — a mismatched id just
     * 404s, the same as it would if the message didn't exist at all.
     */
    public function ownMessageStatus(int $id, string $message): JsonResponse
    {
        $this->activeUserOrFail($id);

        $query = DB::table('messages')->where('user_id', $id)->where('message_uuid', $message);

        if (ctype_digit($message)) {
            $query->orWhere(function ($q) use ($id, $message) {
                $q->where('user_id', $id)->where('id', (int) $message);
            });
        }

        $row = $query->first();

        abort_unless($row, 404, 'No message found with that id.');

        return response()->json([
            'message_id' => $row->message_uuid,
            'service' => $row->service,
            'sender_id' => $row->sender_id_value,
            'destination' => $row->destination_number,
            'country' => $row->destination_country_code,
            'status' => $row->status,
            'is_sent' => (bool) $row->is_sent,
            'reason' => $row->response ?? $row->error_message,
            'submitted_at' => $row->submitted_at,
            'sent_at' => $row->sent_at,
            'delivered_at' => $row->delivered_at,
        ]);
    }

    private function activeUserOrFail(int $id): object
    {
        $user = DB::table('users')->where('id', $id)->where('status', 'active')->first();

        abort_unless($user, 404, 'SMSC account not found');

        return $user;
    }

    private function resolveDateRange(Request $request): array
    {
        $dateTo = $request->query('date_to') ?: now()->toDateString();
        $dateFrom = $request->query('date_from') ?: now()->subDays(30)->toDateString();

        return [$dateFrom, $dateTo];
    }
}
