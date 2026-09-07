WITH cpu_issues AS (

    SELECT
        'missing_cpu_brand_for_active_referenced_model' AS issue_type,
        'CPU' AS entity_type,
        c.cpu_model_id AS entity_id,
        c.cpu_name AS entity_name,
        'warning' AS severity,
        c.is_active AS is_active,
        count(l.laptop_id) > 0 AS is_referenced_by_laptop,
        count(l.laptop_id) AS referencing_laptop_count

    FROM {{ ref('stg_cpu_model') }} AS c

    LEFT JOIN {{ ref('stg_laptop_model') }} AS l
        ON c.cpu_model_id = l.cpu_model_id

    WHERE c.is_active = true
      AND c.cpu_brand_id IS NULL

    GROUP BY
        c.cpu_model_id,
        c.cpu_name,
        c.is_active

    HAVING count(l.laptop_id) > 0

),

gpu_issues AS (

    SELECT
        'missing_gpu_brand_for_active_referenced_model' AS issue_type,
        'GPU' AS entity_type,
        g.gpu_model_id AS entity_id,
        g.gpu_name AS entity_name,
        'warning' AS severity,
        g.is_active AS is_active,
        count(l.laptop_id) > 0 AS is_referenced_by_laptop,
        count(l.laptop_id) AS referencing_laptop_count

    FROM {{ ref('stg_gpu_model') }} AS g

    LEFT JOIN {{ ref('stg_laptop_model') }} AS l
        ON g.gpu_model_id = l.gpu_model_id

    WHERE g.is_active = true
      AND g.gpu_brand_id IS NULL

    GROUP BY
        g.gpu_model_id,
        g.gpu_name,
        g.is_active

    HAVING count(l.laptop_id) > 0

)

SELECT *
FROM cpu_issues

UNION ALL

SELECT *
FROM gpu_issues
