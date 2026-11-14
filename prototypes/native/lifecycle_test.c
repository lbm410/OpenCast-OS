#include "lifecycle.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

typedef struct {
    oc_lifecycle lifecycle;
    unsigned int failures;
    unsigned int reenter;
    unsigned int registrations;
    unsigned int windows;
    unsigned int surfaces;
    unsigned int calls[10];
    char log[64];
    unsigned int length;
} fixture;

static int operation(fixture *f, oc_stage stage, unsigned long generation)
{
    static const char names[] = "?RWSYFLVUT";
    oc_lifecycle *s = &f->lifecycle;
    assert(generation == 71);
    assert(f->length + 1 < sizeof(f->log));
    f->calls[stage] += 1;
    f->log[f->length++] = names[stage];
    f->log[f->length] = 0;
    if (f->reenter) {
        assert(oc_lifecycle_init(s, &s->ops, f, 71) == OC_BUSY);
        assert(oc_lifecycle_admit(s) == OC_BUSY);
        assert(oc_lifecycle_start(s) == OC_BUSY);
        assert(oc_lifecycle_close(s) == OC_BUSY);
        assert(oc_lifecycle_request_focus(s) == OC_BUSY);
        assert(oc_lifecycle_focus_changed(s, 71, s->focus_token, 0) == OC_BUSY);
        assert(oc_lifecycle_return_ack(s, 71, s->return_token, 1) == OC_BUSY);
        assert(oc_lifecycle_timeout(s, 71, s->focus_token) == OC_BUSY);
    }
    /* The synthetic service independently forbids releasing a parent while
     * a child exists, even when that operation would report failure. */
    if (stage == OC_STAGE_WINDOW) assert(f->registrations == 1 && !f->windows);
    if (stage == OC_STAGE_SURFACE) assert(f->windows == 1 && !f->surfaces);
    if (stage == OC_STAGE_RELEASE_WINDOW) assert(f->windows == 1 && !f->surfaces);
    if (stage == OC_STAGE_UNREGISTER) assert(f->registrations == 1 && !f->windows && !f->surfaces);
    if (f->failures & (1U << stage)) return -1;
    if (stage == OC_STAGE_REGISTER) f->registrations += 1;
    if (stage == OC_STAGE_WINDOW) f->windows += 1;
    if (stage == OC_STAGE_RELEASE_WINDOW) f->windows -= 1;
    if (stage == OC_STAGE_SURFACE) f->surfaces += 1;
    if (stage == OC_STAGE_RELEASE) { assert(f->surfaces == 1); f->surfaces -= 1; }
    if (stage == OC_STAGE_UNREGISTER) { assert(f->registrations == 1); f->registrations -= 1; }
    return 0;
}

#define OP(name, stage) static int name(void *c, unsigned long g) { return operation(c, stage, g); }
OP(register_client, OC_STAGE_REGISTER)
OP(acquire_window, OC_STAGE_WINDOW)
OP(acquire_surface, OC_STAGE_SURFACE)
OP(announce_ready, OC_STAGE_READY)
OP(release_surface, OC_STAGE_RELEASE)
OP(release_window, OC_STAGE_RELEASE_WINDOW)
OP(unregister_client, OC_STAGE_UNREGISTER)
static int request_focus(void *c, unsigned long g, unsigned long token)
{
    fixture *f = c;
    assert(token != 0 && token == f->lifecycle.focus_token);
    return operation(f, OC_STAGE_FOCUS, g);
}
static int request_return(void *c, unsigned long g, unsigned long token)
{
    fixture *f = c;
    assert(token != 0 && token == f->lifecycle.return_token);
    return operation(f, OC_STAGE_RETURN, g);
}
static const oc_ops ops = {register_client, acquire_window, acquire_surface, announce_ready,
                          request_focus, release_surface, release_window, unregister_client, request_return};

static void init(fixture *f)
{
    memset(f, 0, sizeof(*f));
    assert(oc_lifecycle_init(&f->lifecycle, &ops, f, 71) == OC_OK);
}
static void start(fixture *f)
{
    init(f);
    assert(oc_lifecycle_admit(&f->lifecycle) == OC_OK);
    assert(oc_lifecycle_start(&f->lifecycle) == OC_OK);
}
static oc_result focus_ack(fixture *f, int granted)
{
    return oc_lifecycle_focus_changed(&f->lifecycle, 71, f->lifecycle.focus_token, granted);
}
static oc_result return_ack(fixture *f, int restored)
{
    return oc_lifecycle_return_ack(&f->lifecycle, 71, f->lifecycle.return_token, restored);
}

static void test_admission_and_arguments(void)
{
    fixture f;
    oc_ops incomplete = ops;
    init(&f);
    assert(oc_lifecycle_init(0, &ops, &f, 71) == OC_BAD_ARGUMENT);
    assert(oc_lifecycle_init(&f.lifecycle, &ops, &f, 0) == OC_BAD_ARGUMENT);
    incomplete.acquire_window = 0;
    assert(oc_lifecycle_init(&f.lifecycle, &incomplete, &f, 71) == OC_BAD_ARGUMENT);
    incomplete = ops; incomplete.release_window = 0;
    assert(oc_lifecycle_init(&f.lifecycle, &incomplete, &f, 71) == OC_BAD_ARGUMENT);
    incomplete = ops; incomplete.acquire_surface = 0;
    assert(oc_lifecycle_init(&f.lifecycle, &incomplete, &f, 71) == OC_BAD_ARGUMENT);
    assert(oc_lifecycle_close(0) == OC_BAD_ARGUMENT);
    assert(oc_lifecycle_init(&f.lifecycle, &ops, &f, 71) == OC_BAD_STATE);
    assert(oc_lifecycle_start(&f.lifecycle) == OC_BAD_STATE);
    assert(f.length == 0);
    assert(oc_lifecycle_close(&f.lifecycle) == OC_OK);
    assert(f.lifecycle.state == OC_CLOSED && f.length == 0);
    assert(oc_lifecycle_admit(&f.lifecycle) == OC_BAD_STATE);
    init(&f);
    assert(oc_lifecycle_admit(&f.lifecycle) == OC_OK);
    assert(oc_lifecycle_admit(&f.lifecycle) == OC_BAD_STATE);
    assert(oc_lifecycle_close(&f.lifecycle) == OC_OK);
    assert(strcmp(f.log, "T") == 0);
    assert(return_ack(&f, 1) == OC_OK);
}

static void test_success_and_exact_cleanup(void)
{
    fixture f;
    start(&f);
    assert(f.lifecycle.state == OC_READY && f.lifecycle.focus_pending);
    assert(strcmp(f.log, "RWSYF") == 0);
    assert(oc_lifecycle_start(&f.lifecycle) == OC_BAD_STATE);
    assert(oc_lifecycle_request_focus(&f.lifecycle) == OC_BAD_STATE);
    assert(focus_ack(&f, 1) == OC_OK && f.lifecycle.state == OC_FOCUSED);
    assert(focus_ack(&f, 1) == OC_BAD_STATE);
    assert(focus_ack(&f, 0) == OC_OK && f.lifecycle.state == OC_READY);
    assert(oc_lifecycle_request_focus(&f.lifecycle) == OC_OK);
    assert(focus_ack(&f, 1) == OC_OK);
    assert(oc_lifecycle_close(&f.lifecycle) == OC_OK);
    assert(strcmp(f.log, "RWSYFFLVUT") == 0);
    assert(!f.surfaces && !f.windows && !f.registrations);
    assert(f.lifecycle.state == OC_RETURN_PENDING);
    assert(oc_lifecycle_close(&f.lifecycle) == OC_OK);
    assert(focus_ack(&f, 0) == OC_BAD_STATE);
    assert(return_ack(&f, 1) == OC_OK && f.lifecycle.state == OC_RETURNED);
    assert(return_ack(&f, 1) == OC_BAD_STATE);
    assert(oc_lifecycle_close(&f.lifecycle) == OC_OK);
    assert(oc_lifecycle_request_focus(&f.lifecycle) == OC_BAD_STATE);
    assert(strcmp(f.log, "RWSYFFLVUT") == 0);
}

static void test_each_start_failure(void)
{
    static const char *expected[] = {"", "RT", "RWUT", "RWSVUT", "RWSYLVUT", "RWSYFLVUT"};
    unsigned int stage;
    for (stage = OC_STAGE_REGISTER; stage <= OC_STAGE_FOCUS; stage += 1) {
        fixture f;
        init(&f); f.failures = 1U << stage;
        assert(oc_lifecycle_admit(&f.lifecycle) == OC_OK);
        assert(oc_lifecycle_start(&f.lifecycle) == OC_ADAPTER_FAILURE);
        assert(f.lifecycle.failure_stage == (oc_stage)stage);
        assert(strcmp(f.log, expected[stage]) == 0);
        assert(!f.surfaces && !f.windows && !f.registrations);
        assert(oc_lifecycle_close(&f.lifecycle) == OC_OK);
        assert(return_ack(&f, 1) == OC_OK);
        assert(f.lifecycle.state == OC_RETURNED);
        assert(strcmp(f.log, expected[stage]) == 0);
    }
}

static void test_each_cleanup_failure(void)
{
    unsigned int stage;
    for (stage = OC_STAGE_RELEASE; stage <= OC_STAGE_RETURN; stage += 1) {
        fixture f;
        start(&f); f.failures = 1U << stage;
        assert(oc_lifecycle_close(&f.lifecycle) == OC_ADAPTER_FAILURE);
        assert(f.lifecycle.failure_stage == (oc_stage)stage);
        const char *expected = stage == OC_STAGE_RELEASE ? "RWSYFLT" :
            stage == OC_STAGE_RELEASE_WINDOW ? "RWSYFLVT" : "RWSYFLVUT";
        assert(strcmp(f.log, expected) == 0);
        assert(f.lifecycle.surface_owned == (stage == OC_STAGE_RELEASE));
        assert(f.lifecycle.window_owned == (stage <= OC_STAGE_RELEASE_WINDOW));
        assert(f.lifecycle.registered == (stage <= OC_STAGE_UNREGISTER));
        assert(f.windows == f.lifecycle.window_owned);
        assert(f.surfaces == f.lifecycle.surface_owned);
        assert(f.registrations == f.lifecycle.registered);
        if (stage != OC_STAGE_RETURN) assert(return_ack(&f, 1) == OC_ADAPTER_FAILURE);
        assert(f.lifecycle.state == OC_FAILED);
        assert(oc_lifecycle_close(&f.lifecycle) == OC_OK);
        assert(focus_ack(&f, 0) == OC_BAD_STATE);
        assert(strcmp(f.log, expected) == 0);
    }
}

static void test_multiple_failures_preserve_ownership_and_first_failure(void)
{
    fixture f;
    init(&f);
    f.failures = (1U << OC_STAGE_READY) | (1U << OC_STAGE_RELEASE) | (1U << OC_STAGE_UNREGISTER);
    assert(oc_lifecycle_admit(&f.lifecycle) == OC_OK);
    assert(oc_lifecycle_start(&f.lifecycle) == OC_ADAPTER_FAILURE);
    assert(f.lifecycle.failure_stage == OC_STAGE_READY);
    assert(f.lifecycle.cleanup_failed && f.lifecycle.surface_owned && f.lifecycle.window_owned && f.lifecycle.registered);
    assert(f.lifecycle.release_attempted && !f.lifecycle.window_release_attempted && !f.lifecycle.unregister_attempted);
    assert(return_ack(&f, 1) == OC_ADAPTER_FAILURE);
    assert(oc_lifecycle_close(&f.lifecycle) == OC_OK);
    assert(f.calls[OC_STAGE_RELEASE] == 1 && f.calls[OC_STAGE_RELEASE_WINDOW] == 0 && f.calls[OC_STAGE_UNREGISTER] == 0);
}

static void test_generation_and_operation_tokens(void)
{
    fixture f;
    unsigned long old;
    start(&f); old = f.lifecycle.focus_token;
    assert(oc_lifecycle_focus_changed(&f.lifecycle, 70, old, 1) == OC_STALE);
    assert(focus_ack(&f, 2) == OC_BAD_ARGUMENT);
    assert(focus_ack(&f, 1) == OC_OK);
    assert(focus_ack(&f, 0) == OC_OK);
    assert(oc_lifecycle_request_focus(&f.lifecycle) == OC_OK);
    assert(oc_lifecycle_focus_changed(&f.lifecycle, 71, old, 1) == OC_STALE);
    assert(oc_lifecycle_timeout(&f.lifecycle, 71, old) == OC_STALE);
    assert(focus_ack(&f, 1) == OC_OK);
    assert(oc_lifecycle_close(&f.lifecycle) == OC_OK);
    assert(oc_lifecycle_return_ack(&f.lifecycle, 71, old, 1) == OC_STALE);
    assert(return_ack(&f, 2) == OC_BAD_ARGUMENT);
    assert(return_ack(&f, 0) == OC_ADAPTER_FAILURE);
    assert(f.lifecycle.state == OC_FAILED);
}

static void test_timeouts_do_not_cross_operation_boundaries(void)
{
    fixture f;
    unsigned long focus;
    start(&f); focus = f.lifecycle.focus_token;
    assert(oc_lifecycle_timeout(&f.lifecycle, 70, focus) == OC_STALE);
    assert(oc_lifecycle_timeout(&f.lifecycle, 71, focus) == OC_TIMEOUT);
    assert(f.lifecycle.state == OC_RETURN_PENDING && !f.lifecycle.surface_owned);
    assert(oc_lifecycle_timeout(&f.lifecycle, 71, focus) == OC_STALE);
    assert(oc_lifecycle_timeout(&f.lifecycle, 71, f.lifecycle.return_token) == OC_TIMEOUT);
    assert(f.lifecycle.state == OC_FAILED);
    assert(return_ack(&f, 1) == OC_BAD_STATE);
    assert(oc_lifecycle_close(&f.lifecycle) == OC_OK);
    assert(strcmp(f.log, "RWSYFLVUT") == 0);
}

static void test_reentrancy_is_rejected_in_every_adapter_operation(void)
{
    fixture f;
    init(&f); f.reenter = 1;
    assert(oc_lifecycle_admit(&f.lifecycle) == OC_OK);
    assert(oc_lifecycle_start(&f.lifecycle) == OC_OK);
    assert(oc_lifecycle_close(&f.lifecycle) == OC_OK);
    assert(strcmp(f.log, "RWSYFLVUT") == 0);
    assert(return_ack(&f, 1) == OC_OK);
}

static void test_focus_retry_failure_and_token_exhaustion(void)
{
    fixture f;
    start(&f);
    assert(focus_ack(&f, 0) == OC_OK);
    f.failures = 1U << OC_STAGE_FOCUS;
    assert(oc_lifecycle_request_focus(&f.lifecycle) == OC_ADAPTER_FAILURE);
    assert(strcmp(f.log, "RWSYFFLVUT") == 0);
    assert(return_ack(&f, 1) == OC_OK);
    start(&f);
    assert(focus_ack(&f, 0) == OC_OK);
    f.lifecycle.serial = ~0UL;
    assert(oc_lifecycle_request_focus(&f.lifecycle) == OC_ADAPTER_FAILURE);
    assert(f.lifecycle.state == OC_FAILED);
    assert(!f.lifecycle.surface_owned && !f.lifecycle.window_owned && !f.lifecycle.registered);
    assert(f.calls[OC_STAGE_FOCUS] == 1 && f.calls[OC_STAGE_RETURN] == 0);
}

static void test_retained_parents_across_timeout_and_late_callbacks(void)
{
    fixture f;
    unsigned int stage;
    for (stage = OC_STAGE_RELEASE; stage <= OC_STAGE_RELEASE_WINDOW; stage += 1) {
        unsigned long focus;
        unsigned int calls;
        start(&f); focus = f.lifecycle.focus_token;
        f.failures = 1U << stage;
        assert(oc_lifecycle_timeout(&f.lifecycle, 71, focus) == OC_TIMEOUT);
        assert(f.lifecycle.failure_stage == OC_STAGE_FOCUS);
        assert(f.lifecycle.cleanup_failed && f.lifecycle.window_owned && f.lifecycle.registered);
        assert(!f.lifecycle.unregister_attempted);
        assert(f.lifecycle.surface_owned == (stage == OC_STAGE_RELEASE));
        assert(f.lifecycle.window_release_attempted == (stage == OC_STAGE_RELEASE_WINDOW));
        calls = f.length;
        assert(oc_lifecycle_focus_changed(&f.lifecycle, 71, focus, 1) == OC_BAD_STATE);
        assert(oc_lifecycle_return_ack(&f.lifecycle, 70, f.lifecycle.return_token, 1) == OC_STALE);
        assert(oc_lifecycle_close(&f.lifecycle) == OC_OK);
        assert(oc_lifecycle_timeout(&f.lifecycle, 71, focus) == OC_STALE);
        assert(oc_lifecycle_timeout(&f.lifecycle, 71, f.lifecycle.return_token) == OC_TIMEOUT);
        assert(return_ack(&f, 1) == OC_BAD_STATE);
        assert(oc_lifecycle_close(&f.lifecycle) == OC_OK);
        assert(f.length == calls && f.lifecycle.state == OC_FAILED);
        assert(f.windows == 1 && f.registrations == 1);
    }
}

int main(void)
{
    test_admission_and_arguments();
    test_success_and_exact_cleanup();
    test_each_start_failure();
    test_each_cleanup_failure();
    test_multiple_failures_preserve_ownership_and_first_failure();
    test_generation_and_operation_tokens();
    test_timeouts_do_not_cross_operation_boundaries();
    test_reentrancy_is_rejected_in_every_adapter_operation();
    test_focus_retry_failure_and_token_exhaustion();
    test_retained_parents_across_timeout_and_late_callbacks();
    puts("10 lifecycle test groups passed (all 9 adapter failure stages covered)");
    return 0;
}
