#include "lifecycle.h"

static oc_result check(const oc_lifecycle *self)
{
    if (!self || !self->initialized) return OC_BAD_ARGUMENT;
    if (self->busy) return OC_BUSY;
    return OC_OK;
}

static oc_result event_check(const oc_lifecycle *self, unsigned long generation)
{
    oc_result result = check(self);
    if (result != OC_OK) return result;
    return generation == self->generation ? OC_OK : OC_STALE;
}

static void failure(oc_lifecycle *self, oc_stage stage)
{
    if (self->failure_stage == OC_STAGE_NONE) self->failure_stage = stage;
}

static unsigned long next_token(oc_lifecycle *self)
{
    if (self->serial == ~0UL) return 0;
    self->serial += 1;
    return self->serial;
}

static oc_result close_internal(oc_lifecycle *self)
{
    int result;
    self->busy = 1;
    self->focus_pending = 0;
    if (self->surface_owned && !self->release_attempted) {
        self->release_attempted = 1;
        result = self->ops.release_surface(self->context, self->generation);
        if (result == 0) self->surface_owned = 0;
        else { self->cleanup_failed = 1; failure(self, OC_STAGE_RELEASE); }
    }
    if (!self->surface_owned && self->window_owned && !self->window_release_attempted) {
        self->window_release_attempted = 1;
        result = self->ops.release_window(self->context, self->generation);
        if (result == 0) self->window_owned = 0;
        else { self->cleanup_failed = 1; failure(self, OC_STAGE_RELEASE_WINDOW); }
    }
    if (!self->surface_owned && !self->window_owned && self->registered && !self->unregister_attempted) {
        self->unregister_attempted = 1;
        result = self->ops.unregister_client(self->context, self->generation);
        if (result == 0) self->registered = 0;
        else { self->cleanup_failed = 1; failure(self, OC_STAGE_UNREGISTER); }
    }
    self->return_token = next_token(self);
    result = self->return_token ? self->ops.request_return(self->context, self->generation, self->return_token) : -1;
    if (result != 0) { failure(self, OC_STAGE_RETURN); self->state = OC_FAILED; }
    else self->state = OC_RETURN_PENDING;
    self->busy = 0;
    return result != 0 || self->cleanup_failed ? OC_ADAPTER_FAILURE : OC_OK;
}

oc_result oc_lifecycle_init(oc_lifecycle *self, const oc_ops *ops,
                            void *context, unsigned long generation)
{
    if (!self || !ops || !generation || !ops->register_client ||
        !ops->acquire_window || !ops->acquire_surface || !ops->announce_ready || !ops->request_focus ||
        !ops->release_surface || !ops->release_window || !ops->unregister_client || !ops->request_return)
        return OC_BAD_ARGUMENT;
    if (self->initialized) return self->busy ? OC_BUSY : OC_BAD_STATE;
    self->ops = *ops;
    self->context = context;
    self->generation = generation;
    self->serial = 0;
    self->focus_token = 0;
    self->return_token = 0;
    self->state = OC_NEW;
    self->failure_stage = OC_STAGE_NONE;
    self->registered = 0;
    self->window_owned = 0;
    self->surface_owned = 0;
    self->release_attempted = 0;
    self->window_release_attempted = 0;
    self->unregister_attempted = 0;
    self->cleanup_failed = 0;
    self->focus_pending = 0;
    self->busy = 0;
    self->initialized = 1;
    return OC_OK;
}

oc_result oc_lifecycle_admit(oc_lifecycle *self)
{
    oc_result result = check(self);
    if (result != OC_OK) return result;
    if (self->state != OC_NEW) return OC_BAD_STATE;
    self->state = OC_ADMITTED;
    return OC_OK;
}

oc_result oc_lifecycle_start(oc_lifecycle *self)
{
    oc_result result = check(self);
    oc_stage stage = OC_STAGE_REGISTER;
    if (result != OC_OK) return result;
    if (self->state != OC_ADMITTED) return OC_BAD_STATE;
    self->busy = 1;
    if (self->ops.register_client(self->context, self->generation) != 0) goto failed;
    self->registered = 1;
    self->state = OC_REGISTERED;
    stage = OC_STAGE_WINDOW;
    if (self->ops.acquire_window(self->context, self->generation) != 0) goto failed;
    self->window_owned = 1;
    self->state = OC_WINDOW;
    stage = OC_STAGE_SURFACE;
    if (self->ops.acquire_surface(self->context, self->generation) != 0) goto failed;
    self->surface_owned = 1;
    self->state = OC_SURFACE;
    stage = OC_STAGE_READY;
    if (self->ops.announce_ready(self->context, self->generation) != 0) goto failed;
    self->state = OC_READY;
    stage = OC_STAGE_FOCUS;
    self->focus_token = next_token(self);
    if (!self->focus_token || self->ops.request_focus(self->context, self->generation, self->focus_token) != 0) goto failed;
    self->focus_pending = 1;
    self->busy = 0;
    return OC_OK;
failed:
    failure(self, stage);
    self->busy = 0;
    (void)close_internal(self);
    return OC_ADAPTER_FAILURE;
}

oc_result oc_lifecycle_request_focus(oc_lifecycle *self)
{
    int requested;
    oc_result result = check(self);
    if (result != OC_OK) return result;
    if (self->state != OC_READY || self->focus_pending) return OC_BAD_STATE;
    self->busy = 1;
    self->focus_token = next_token(self);
    requested = self->focus_token ? self->ops.request_focus(self->context, self->generation, self->focus_token) : -1;
    self->busy = 0;
    if (requested != 0) {
        failure(self, OC_STAGE_FOCUS);
        (void)close_internal(self);
        return OC_ADAPTER_FAILURE;
    }
    self->focus_pending = 1;
    return OC_OK;
}

oc_result oc_lifecycle_close(oc_lifecycle *self)
{
    oc_result result = check(self);
    if (result != OC_OK) return result;
    if (self->state == OC_RETURN_PENDING || self->state == OC_RETURNED ||
        self->state == OC_CLOSED || self->state == OC_FAILED) return OC_OK;
    if (self->state == OC_NEW) { self->state = OC_CLOSED; return OC_OK; }
    return close_internal(self);
}

oc_result oc_lifecycle_focus_changed(oc_lifecycle *self, unsigned long generation, unsigned long token, int focused)
{
    oc_result result = event_check(self, generation);
    if (result != OC_OK) return result;
    if (!token || token != self->focus_token) return OC_STALE;
    if (focused != 0 && focused != 1) return OC_BAD_ARGUMENT;
    if (self->state != OC_READY && self->state != OC_FOCUSED) return OC_BAD_STATE;
    if (focused && !self->focus_pending) return OC_BAD_STATE;
    self->focus_pending = 0;
    self->state = focused ? OC_FOCUSED : OC_READY;
    return OC_OK;
}

oc_result oc_lifecycle_return_ack(oc_lifecycle *self, unsigned long generation, unsigned long token, int restored)
{
    oc_result result = event_check(self, generation);
    if (result != OC_OK) return result;
    if (!token || token != self->return_token) return OC_STALE;
    if (restored != 0 && restored != 1) return OC_BAD_ARGUMENT;
    if (self->state != OC_RETURN_PENDING) return OC_BAD_STATE;
    if (!restored) failure(self, OC_STAGE_RETURN);
    self->state = restored && !self->cleanup_failed ? OC_RETURNED : OC_FAILED;
    return self->state == OC_RETURNED ? OC_OK : OC_ADAPTER_FAILURE;
}

oc_result oc_lifecycle_timeout(oc_lifecycle *self, unsigned long generation, unsigned long token)
{
    oc_result result = event_check(self, generation);
    if (result != OC_OK) return result;
    if (!token) return OC_STALE;
    if (self->state == OC_RETURN_PENDING) {
        if (token != self->return_token) return OC_STALE;
        failure(self, OC_STAGE_RETURN);
        self->state = OC_FAILED;
        return OC_TIMEOUT;
    }
    if (token != self->focus_token) return OC_STALE;
    if (self->state != OC_READY || !self->focus_pending) return OC_BAD_STATE;
    failure(self, OC_STAGE_FOCUS);
    (void)close_internal(self);
    return OC_TIMEOUT;
}
