package com.fieldverify.reader.ui;

import android.content.Intent;
import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.Menu;
import android.view.MenuItem;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import com.fieldverify.reader.FieldVerifyApp;
import com.fieldverify.reader.R;
import com.fieldverify.reader.api.BackendClient;
import com.fieldverify.reader.api.Models;

import java.util.ArrayList;
import java.util.List;

/** Today's site visits, from GET /api/visits. Tap one to verify the provider in person. */
public class MainActivity extends BaseActivity implements FieldVerifyApp.ReaderStateListener {

    private FieldVerifyApp app;
    private TextView readerStatus;
    private TextView listMessage;
    private final VisitAdapter adapter = new VisitAdapter();

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setUpScreen(R.layout.activity_main, false);
        app = FieldVerifyApp.from(this);
        readerStatus = findViewById(R.id.reader_status);
        listMessage = findViewById(R.id.list_message);
        TextView server = findViewById(R.id.server_url);
        server.setText(getString(R.string.server_label, app.backend().getBaseUrl()));

        List<String> missing = app.missingConfig();
        TextView configWarning = findViewById(R.id.config_warning);
        if (!missing.isEmpty()) {
            configWarning.setVisibility(View.VISIBLE);
            configWarning.setText(getString(R.string.config_missing, String.join(", ", missing)));
        }

        RecyclerView list = findViewById(R.id.visit_list);
        list.setLayoutManager(new LinearLayoutManager(this));
        list.setAdapter(adapter);
        readerStatus.setOnClickListener(v -> {
            if (app.readerState() == FieldVerifyApp.ReaderState.FAILED) {
                app.initReader();
            }
        });
    }

    @Override
    protected void onStart() {
        super.onStart();
        app.addReaderStateListener(this);
        loadVisits();
    }

    @Override
    protected void onStop() {
        app.removeReaderStateListener(this);
        super.onStop();
    }

    @Override
    public boolean onCreateOptionsMenu(Menu menu) {
        menu.add(0, 1, 0, R.string.refresh).setShowAsAction(MenuItem.SHOW_AS_ACTION_ALWAYS);
        return true;
    }

    @Override
    public boolean onOptionsItemSelected(@NonNull MenuItem item) {
        if (item.getItemId() == 1) {
            loadVisits();
            return true;
        }
        return super.onOptionsItemSelected(item);
    }

    @Override
    public void onReaderStateChanged(FieldVerifyApp.ReaderState state, @Nullable String detail) {
        switch (state) {
            case READY:
                readerStatus.setText(getString(R.string.reader_ready, detail));
                readerStatus.setBackgroundResource(R.drawable.bg_status_green);
                break;
            case INITIALIZING:
                readerStatus.setText(R.string.reader_initializing);
                readerStatus.setBackgroundResource(R.drawable.bg_status_neutral);
                break;
            case NOT_CONFIGURED:
            case FAILED:
            default:
                readerStatus.setText(getString(R.string.reader_failed, detail));
                readerStatus.setBackgroundResource(R.drawable.bg_status_red);
                break;
        }
    }

    private void loadVisits() {
        listMessage.setVisibility(View.VISIBLE);
        listMessage.setText(R.string.loading_visits);
        app.backend().listVisits(new BackendClient.Callback<List<Models.Visit>>() {
            @Override
            public void onSuccess(List<Models.Visit> visits) {
                adapter.setVisits(visits);
                listMessage.setVisibility(visits.isEmpty() ? View.VISIBLE : View.GONE);
                listMessage.setText(R.string.no_visits);
            }

            @Override
            public void onError(String message) {
                listMessage.setVisibility(View.VISIBLE);
                listMessage.setText(message);
            }
        });
    }

    private void openVisit(Models.Visit visit) {
        Intent intent = new Intent(this, VerifyActivity.class);
        intent.putExtra(VerifyActivity.EXTRA_VISIT_JSON, BackendClient.GSON.toJson(visit));
        startActivity(intent);
    }

    private class VisitAdapter extends RecyclerView.Adapter<VisitAdapter.Holder> {
        private final List<Models.Visit> visits = new ArrayList<>();

        void setVisits(List<Models.Visit> items) {
            visits.clear();
            visits.addAll(items);
            notifyDataSetChanged();
        }

        @NonNull
        @Override
        public Holder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
            View v = LayoutInflater.from(parent.getContext()).inflate(R.layout.item_visit, parent, false);
            return new Holder(v);
        }

        @Override
        public void onBindViewHolder(@NonNull Holder h, int position) {
            Models.Visit visit = visits.get(position);
            h.time.setText(Format.visitTime(visit.scheduledAt));
            h.name.setText(visit.provider.name);
            h.details.setText(getString(R.string.visit_details, visit.provider.npi, visit.provider.specialty));
            h.address.setText(visit.siteAddress);
            h.risk.setText(Format.title(visit.provider.riskLevel) + " risk");
            h.status.setText(Format.title(visit.status));
            h.itemView.setOnClickListener(v -> openVisit(visit));
        }

        @Override
        public int getItemCount() {
            return visits.size();
        }

        class Holder extends RecyclerView.ViewHolder {
            final TextView time;
            final TextView name;
            final TextView details;
            final TextView address;
            final TextView risk;
            final TextView status;

            Holder(View v) {
                super(v);
                time = v.findViewById(R.id.visit_time);
                name = v.findViewById(R.id.visit_name);
                details = v.findViewById(R.id.visit_details);
                address = v.findViewById(R.id.visit_address);
                risk = v.findViewById(R.id.visit_risk);
                status = v.findViewById(R.id.visit_status);
            }
        }
    }
}
