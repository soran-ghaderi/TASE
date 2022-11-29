from aioarango.typings import Json


def format_aql_query(body: Json) -> Json:
    """
    Format AQL query data.

    Parameters
    ----------
    body : dict
        Input body.

    Returns
    -------
    dict
        Formatted body.

    """
    result = {
        "id": body["id"],
        "query": body["query"],
    }
    if "database" in body:
        result["database"] = body["database"]
    if "bindVars" in body:
        result["bind_vars"] = body["bindVars"]
    if "runTime" in body:
        print(body["runTime"])
        result["runtime"] = body["runTime"]
    if "started" in body:
        result["started"] = body["started"]
    if "state" in body:
        result["state"] = body["state"]
    if "stream" in body:
        result["stream"] = body["stream"]
    if "user" in body:
        result["user"] = body["user"]

    return result


def format_aql_tracking(body: Json) -> Json:
    """
    Format AQL tracking data.

    Parameters
    ----------
    body : Json
        Input body.

    Returns
    -------
    Json
        Formatted body.
    """
    result: Json = {}
    if "enabled" in body:
        result["enabled"] = body["enabled"]
    if "maxQueryStringLength" in body:
        result["max_query_string_length"] = body["maxQueryStringLength"]
    if "maxSlowQueries" in body:
        result["max_slow_queries"] = body["maxSlowQueries"]
    if "slowQueryThreshold" in body:
        result["slow_query_threshold"] = body["slowQueryThreshold"]
    if "slowStreamingQueryThreshold" in body:
        result["slow_streaming_query_threshold"] = body["slowStreamingQueryThreshold"]
    if "trackBindVars" in body:
        result["track_bind_vars"] = body["trackBindVars"]
    if "trackSlowQueries" in body:
        result["track_slow_queries"] = body["trackSlowQueries"]

    return result
