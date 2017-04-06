from .descriptor import Descriptor

class ThirdPartyDescriptor(Descriptor):
    """
    Descriptor that describes a Third Party Application (generic path to executable or library)
    """

    def __init__(self, io_descriptor):
        """
        Use the factory method :meth:`create_descriptor` when
        creating new descriptor objects.

        :param io_descriptor: Associated IO descriptor.
        """
        super(ThirdPartyDescriptor, self).__init__(io_descriptor)