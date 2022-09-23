
def get_pis_app_id(acquirer_sudo):
    """ Return the publishable key for Fintecture PIS Application.

    Note: This method serves as a hook for modules that would fully implement Fintecture Connect.

    :param recordset acquirer_sudo: The acquirer on which the key should be read, as a sudoed
                                    `payment.acquire` record.
    :return: The publishable PIS key
    :rtype: str
    """
    return acquirer_sudo.fintecture_pis_app_id


def get_pis_app_secret(acquirer_sudo):
    """ Return the application secret key for Fintecture PIS Application.

    Note: This method serves as a hook for modules that would fully implement Fintecture Connect.

    :param recordset acquirer_sudo: The acquirer on which the key should be read, as a sudoed
                                    `payment.acquire` record.
    :return: The application PIS secret key
    :rtype: str
    """
    return acquirer_sudo.fintecture_pis_app_secret


def get_pis_private_key(acquirer_sudo):
    """ Return the private key for Fintecture PIS Application.

    Note: This method serves as a hook for modules that would fully implement Fintecture Connect.

    :param recordset acquirer_sudo: The acquirer on which the key should be read, as a sudoed
                                    `payment.acquire` record.
    :returns: The private PIS key
    :rtype: binary file content
    """
    return acquirer_sudo.fintecture_pis_private_key_file
