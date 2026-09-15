<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use Carbon\Carbon;
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
            'connection_status' => $smpp->connection_status,
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
            ->join('services', 'services.id', '=', 'user_services.service_id')
            ->where('user_services.user_id', $userId)
            ->where('services.slug', $service)
            ->select('user_services.*', 'services.slug as service')
            ->first();
    }

    /**
     * @return array<string, object>
     */
    private function servicesFor(int $userId): array
    {
        return DB::table('user_services')
            ->join('services', 'services.id', '=', 'user_services.service_id')
            ->where('user_services.user_id', $userId)
            ->select('user_services.*', 'services.slug as service')
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
                'connection_status' => $smpp->connection_status,
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

    /**
     * Backs Sender ID questions ("was my sender ID approved", "which
     * countries is it enabled for") with the visitor's real rows instead
     * of the chatbot having to guess or send them off to check a page
     * that doesn't exist for this demo.
     */
    public function senderIds(int $id): JsonResponse
    {
        $this->activeUserOrFail($id);

        $senderIds = DB::table('sender_ids')->where('user_id', $id)->orderBy('sender_id')->get();

        return response()->json([
            'sender_ids' => $senderIds->map(function ($row) {
                $countries = DB::table('sender_id_countries')
                    ->join('countries', 'countries.id', '=', 'sender_id_countries.country_id')
                    ->where('sender_id_countries.sender_id_id', $row->id)
                    ->orderBy('countries.country_name')
                    ->get(['countries.country_name', 'countries.iso_code', 'sender_id_countries.enabled']);

                return [
                    'sender_id' => $row->sender_id,
                    'sender_type' => $row->sender_type,
                    'status' => $row->status,
                    'approved_at' => $row->approved_at,
                    'countries' => $countries->map(fn ($c) => [
                        'country' => $c->country_name,
                        'iso_code' => $c->iso_code,
                        'enabled' => (bool) $c->enabled,
                    ]),
                ];
            }),
        ]);
    }

    /**
     * `sms_usage` (a pre-aggregated daily-usage table) is referenced nowhere
     * else in this codebase — no migration, model, or seeder ever creates
     * it, so this endpoint would throw a "table not found" error the first
     * time it was actually called. `messages` (see App\Models\Traffic)
     * already has everything needed — user_id, status, is_sent,
     * submitted_at — so both report endpoints below are read straight off
     * it instead, with a day-by-day breakdown for charting (see
     * chatbot-ai smsc_ai_service's chart-building, which needs real
     * per-day points, not just a range total).
     */
    public function traffic(int $id, Request $request): JsonResponse
    {
        $this->activeUserOrFail($id);

        [$dateFrom, $dateTo] = $this->resolveDateRange($request);

        $rows = DB::table('messages')
            ->where('user_id', $id)
            ->whereBetween('submitted_at', ["{$dateFrom} 00:00:00", "{$dateTo} 23:59:59"])
            ->selectRaw("
                DATE(submitted_at) as usage_date,
                COUNT(*) as total_submitted,
                SUM(CASE WHEN is_sent THEN 1 ELSE 0 END) as total_sent,
                SUM(CASE WHEN status = 'DELIVERED' THEN 1 ELSE 0 END) as total_delivered,
                SUM(CASE WHEN status IN ('FAILED', 'EXPIRED', 'REJECTED') THEN 1 ELSE 0 END) as total_failed
            ")
            ->groupBy('usage_date')
            ->get()
            ->keyBy(fn ($row) => (string) $row->usage_date);

        $daily = [];
        $totalSubmitted = $totalSent = $totalDelivered = $totalFailed = 0;
        foreach ($this->dailyDateRange($dateFrom, $dateTo) as $date) {
            $row = $rows->get($date);
            $submitted = (int) ($row->total_submitted ?? 0);
            $sent = (int) ($row->total_sent ?? 0);
            $delivered = (int) ($row->total_delivered ?? 0);
            $failed = (int) ($row->total_failed ?? 0);

            $daily[] = compact('date', 'submitted', 'sent', 'delivered', 'failed');
            $totalSubmitted += $submitted;
            $totalSent += $sent;
            $totalDelivered += $delivered;
            $totalFailed += $failed;
        }

        return response()->json([
            'date_from' => $dateFrom,
            'date_to' => $dateTo,
            'total_submitted' => $totalSubmitted,
            'total_sent' => $totalSent,
            'total_delivered' => $totalDelivered,
            'total_failed' => $totalFailed,
            'daily' => $daily,
        ]);
    }

    public function deliveryStats(int $id, Request $request): JsonResponse
    {
        $this->activeUserOrFail($id);

        [$dateFrom, $dateTo] = $this->resolveDateRange($request);

        $rows = DB::table('messages')
            ->where('user_id', $id)
            ->whereBetween('submitted_at', ["{$dateFrom} 00:00:00", "{$dateTo} 23:59:59"])
            ->selectRaw("
                DATE(submitted_at) as usage_date,
                SUM(CASE WHEN is_sent THEN 1 ELSE 0 END) as total_sent,
                SUM(CASE WHEN status = 'DELIVERED' THEN 1 ELSE 0 END) as total_delivered,
                SUM(CASE WHEN status IN ('FAILED', 'EXPIRED', 'REJECTED') THEN 1 ELSE 0 END) as total_failed
            ")
            ->groupBy('usage_date')
            ->get()
            ->keyBy(fn ($row) => (string) $row->usage_date);

        $daily = [];
        $sent = $delivered = $failed = 0;
        foreach ($this->dailyDateRange($dateFrom, $dateTo) as $date) {
            $row = $rows->get($date);
            $daySent = (int) ($row->total_sent ?? 0);
            $dayDelivered = (int) ($row->total_delivered ?? 0);
            $dayFailed = (int) ($row->total_failed ?? 0);
            $dayRate = $daySent > 0 ? round(($dayDelivered / $daySent) * 100, 2) : null;

            $daily[] = [
                'date' => $date,
                'sent' => $daySent,
                'delivered' => $dayDelivered,
                'failed' => $dayFailed,
                'delivery_rate_percent' => $dayRate,
            ];
            $sent += $daySent;
            $delivered += $dayDelivered;
            $failed += $dayFailed;
        }
        $deliveryRate = $sent > 0 ? round(($delivered / $sent) * 100, 2) : null;

        return response()->json([
            'date_from' => $dateFrom,
            'date_to' => $dateTo,
            'sent' => $sent,
            'delivered' => $delivered,
            'failed' => $failed,
            'delivery_rate_percent' => $deliveryRate,
            'daily' => $daily,
        ]);
    }

    /**
     * Groups the same real per-message data traffic()/deliveryStats() read
     * — by destination country or by sender ID — for the chatbot's "By
     * Country"/"By Sender ID" drill-down buttons. `by=sender_id` isn't
     * scoped further since a user only ever has their own sender ids
     * anyway (enforced by `where('user_id', $id)` below, same as every
     * other endpoint here).
     */
    public function trafficBreakdown(int $id, Request $request): JsonResponse
    {
        $this->activeUserOrFail($id);

        $by = $request->query('by', 'country');
        abort_unless(in_array($by, ['country', 'sender_id'], true), 422, 'Invalid by parameter.');

        [$dateFrom, $dateTo] = $this->resolveDateRange($request);
        $groupColumn = $by === 'country' ? 'destination_country_code' : 'sender_id_value';

        $rows = DB::table('messages')
            ->where('user_id', $id)
            ->whereBetween('submitted_at', ["{$dateFrom} 00:00:00", "{$dateTo} 23:59:59"])
            ->selectRaw("
                {$groupColumn} as `group`,
                COUNT(*) as submitted,
                SUM(CASE WHEN status = 'DELIVERED' THEN 1 ELSE 0 END) as delivered,
                SUM(CASE WHEN status IN ('FAILED', 'EXPIRED', 'REJECTED') THEN 1 ELSE 0 END) as failed
            ")
            ->groupBy('group')
            ->orderByDesc('submitted')
            ->get();

        return response()->json([
            'by' => $by,
            'date_from' => $dateFrom,
            'date_to' => $dateTo,
            'groups' => $rows->map(fn ($r) => [
                'label' => $r->group,
                'submitted' => (int) $r->submitted,
                'delivered' => (int) $r->delivered,
                'failed' => (int) $r->failed,
                'delivery_rate_percent' => $r->submitted > 0 ? round(($r->delivered / $r->submitted) * 100, 2) : null,
            ]),
        ]);
    }

    /**
     * Consolidated failure breakdown for the chatbot's "Failure Analysis"
     * button: same failed messages traffic()/deliveryStats() already
     * count, grouped three ways (reason, country, sender ID) in one call
     * so the AI doesn't need three separate round trips. `top_reason` is
     * computed here (not left to the model) so it's never a guess.
     */
    public function failureAnalysis(int $id, Request $request): JsonResponse
    {
        $this->activeUserOrFail($id);

        [$dateFrom, $dateTo] = $this->resolveDateRange($request);

        $base = fn () => DB::table('messages')
            ->where('user_id', $id)
            ->whereIn('status', ['FAILED', 'EXPIRED', 'REJECTED'])
            ->whereBetween('submitted_at', ["{$dateFrom} 00:00:00", "{$dateTo} 23:59:59"]);

        $totalFailed = $base()->count();

        $byReason = $base()
            ->selectRaw("COALESCE(error_message, status) as reason, COUNT(*) as count")
            ->groupBy('reason')->orderByDesc('count')->limit(5)->get();

        $byCountry = $base()
            ->selectRaw("destination_country_code as country, COUNT(*) as count")
            ->groupBy('country')->orderByDesc('count')->limit(5)->get();

        $bySenderId = $base()
            ->selectRaw("sender_id_value as sender_id, COUNT(*) as count")
            ->groupBy('sender_id')->orderByDesc('count')->limit(5)->get();

        return response()->json([
            'date_from' => $dateFrom,
            'date_to' => $dateTo,
            'total_failed' => $totalFailed,
            'top_reason' => $byReason->first()->reason ?? null,
            'by_reason' => $byReason->map(fn ($r) => ['label' => $r->reason, 'count' => (int) $r->count]),
            'by_country' => $byCountry->map(fn ($r) => ['label' => $r->country, 'count' => (int) $r->count]),
            'by_sender_id' => $bySenderId->map(fn ($r) => ['label' => $r->sender_id, 'count' => (int) $r->count]),
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
     * Platform-wide product/service catalog, not user-scoped — same list
     * for every prospect. Backs the chatbot's Sales menu so it always
     * offers every real product instead of a hand-maintained subset.
     */
    public function services(): JsonResponse
    {
        $rows = DB::table('services')
            ->orderByRaw("field(category, 'messaging', 'tool')")
            ->orderBy('name')
            ->get(['slug', 'name', 'category', 'description']);

        return response()->json([
            'services' => $rows->map(fn ($r) => [
                'slug' => $r->slug,
                'name' => $r->name,
                'category' => $r->category,
                'description' => $r->description,
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

    /**
     * Every calendar date from $dateFrom to $dateTo inclusive, so a day
     * with zero messages still shows up as a zero point in `daily` instead
     * of silently disappearing — a chart built from this shouldn't look
     * like traffic stopped when it just wasn't grouped.
     */
    private function dailyDateRange(string $dateFrom, string $dateTo): array
    {
        $dates = [];
        $cursor = Carbon::parse($dateFrom)->startOfDay();
        $end = Carbon::parse($dateTo)->startOfDay();
        while ($cursor->lte($end)) {
            $dates[] = $cursor->toDateString();
            $cursor->addDay();
        }

        return $dates;
    }
}
