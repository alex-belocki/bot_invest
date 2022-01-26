rate_partners_query = '''
    SELECT num_row, tt.partners_cnt
    FROM 
         (SELECT 
            ROW_NUMBER() OVER(ORDER BY grouped_data.partners_cnt DESC, users.last_partner_registered) AS num_row,
            grouped_data.super_partner_id, 
            grouped_data.partners_cnt, 
            users.sex
        FROM 
            (SELECT
                super_partner_id, COUNT(user_id) AS partners_cnt
            FROM
                users
            GROUP BY 
                super_partner_id
             ) AS grouped_data
         JOIN
            users
         ON
            grouped_data.super_partner_id=users.user_id) AS tt
    WHERE super_partner_id={}'''


super_partners_count_query = '''
    SELECT MAX(grouped_data.row_num)
    FROM
    (SELECT
        super_partner_id, ROW_NUMBER() OVER() AS row_num, COUNT(user_id) AS partners_cnt
    FROM
        users
    WHERE 
        super_partner_id is not NULL
    GROUP BY 
        super_partner_id) AS grouped_data;'''


raw_without_parnters_query = ''' 
    SELECT row_num, grouped_data.partners_cnt
    FROM
        (SELECT 
            {sp_count} + ROW_NUMBER() OVER(ORDER BY date_start) AS row_num, user_id, 
            0 AS partners_cnt
        FROM users
        WHERE user_id NOT IN (SELECT DISTINCT super_partner_id
                              FROM users
                              WHERE super_partner_id IS NOT NULL)
        ) AS grouped_data
    WHERE user_id={user_id}
;'''

top_partners_list_query = ''' 
    SELECT row_num, super_partner_id, partners_cnt, sex
    from
        (SELECT 
            ROW_NUMBER() OVER(ORDER BY grouped_data.partners_cnt DESC, users.last_partner_registered) AS row_num,
            grouped_data.super_partner_id, 
            grouped_data.partners_cnt, 
            users.sex
        FROM 
            (SELECT
                super_partner_id, COUNT(user_id) AS partners_cnt
            FROM
                users
            GROUP BY 
                super_partner_id
             ) AS grouped_data
         JOIN
            users
         ON
            grouped_data.super_partner_id=users.user_id

         ) as p_table

    UNION

        SELECT {sp_count} + row_num, user_id, grouped_data.partners_cnt, grouped_data.sex
            FROM
            (SELECT ROW_NUMBER() OVER(ORDER BY date_start) AS row_num, user_id, 0 AS partners_cnt, sex
            FROM users
            WHERE user_id NOT IN (SELECT DISTINCT super_partner_id
                                  FROM users
                                  WHERE super_partner_id IS NOT NULL)
            ) as grouped_data

    ORDER BY row_num
    LIMIT 100
'''



