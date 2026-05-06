-- Run once in Supabase Dashboard → SQL Editor

create table if not exists tenders (
    tender_id               text primary key,
    tender_no               text,
    title                   text,
    publish_date            text,
    submission_deadline     text,
    bid_opening_date        text,
    source_url              text,
    status                  text default 'active',
    fetched_at              timestamptz default now(),

    -- Extra fields from tenderdetail API
    date_published          text,
    bid_submission_start    text,
    priced_bid_opening      text,
    pre_bid_meeting         text,
    doc_sales_start         text,
    doc_sales_end           text,
    tender_type             text,
    procurement_cat         text,
    evaluation_type         text,
    application_fee         text,
    emd_value               text,

    raw_detail              jsonb
);

create table if not exists tender_analysis (
    tender_id   text primary key references tenders(tender_id),
    analysis    jsonb not null,
    analyzed_at timestamptz default now()
);

create table if not exists tender_documents (
    id            bigserial primary key,
    tender_id     text references tenders(tender_id),
    filename      text not null,
    description   text,
    url           text,
    filesize      text,
    extension     text,
    supabase_path text,
    is_form       boolean default false,
    uploaded_at   timestamptz default now(),
    unique (tender_id, filename)
);

-- After running this SQL:
-- Go to Storage → Create bucket named "tender-documents" → set Public = true
