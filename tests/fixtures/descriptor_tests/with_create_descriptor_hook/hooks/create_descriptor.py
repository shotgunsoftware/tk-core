
from sgtk import get_hook_baseclass
from sgtk.descriptor import create_descriptor


class CreateDescriptorHook(get_hook_baseclass()):
    def create_descriptor(
        self,
        sg_connection,
        descriptor_type,
        dict_or_uri,
        bundle_cache_root_override,
        fallback_roots,
        resolve_latest,
        constraint_pattern,
        local_fallback_when_disconnected,
        **kwargs
    ):
        assert len(kwargs) == 0
        desc = create_descriptor(
            sg_connection,
            descriptor_type,
            dict_or_uri,
            bundle_cache_root_override,
            fallback_roots,
            resolve_latest,
            constraint_pattern,
            local_fallback_when_disconnected
        )
        desc.created_through_hook = True
        desc.parent = self.parent
        return desc
