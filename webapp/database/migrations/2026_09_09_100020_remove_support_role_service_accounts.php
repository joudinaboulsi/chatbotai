<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

/**
 * Support-role users have no SMSC account of their own (see users.role,
 * where support staff have account_id/customer_id both NULL) — but the
 * demo seed data still gave them user_services rows (smpp/api/hlr), as if
 * they were a tenant with a real account. Only "user"-role rows should
 * exist here; a support login now has none, so there's nothing for the
 * account-scoped SMSC tools to (incorrectly) find for them — see
 * chatbot-ai's smsc_service._ACCOUNT_SCOPED_TOOLS enforcement.
 */
return new class extends Migration
{
    public function up(): void
    {
        $supportUserIds = DB::table('users')->where('role', 'support')->pluck('id');

        DB::table('user_services')->whereIn('user_id', $supportUserIds)->delete();
    }

    public function down(): void
    {
        // Deleted rows carried no data worth restoring (they were always
        // meant to not exist), so there is nothing to reverse here.
    }
};
