package com.fieldverify.reader.ui;

import android.graphics.Color;

import androidx.activity.EdgeToEdge;
import androidx.activity.SystemBarStyle;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowInsetsCompat;

import com.fieldverify.reader.R;
import com.google.android.material.appbar.MaterialToolbar;

/**
 * Shared screen setup. Android 15+ draws apps edge to edge (behind the status and navigation bars), so the toolbar is
 * padded by the status-bar height and the screen by the navigation bar / keyboard.
 */
abstract class BaseActivity extends AppCompatActivity {

    protected void setUpScreen(int layoutRes, boolean showUp) {
        // Dark style = white status-bar icons over the brand-colored toolbar.
        EdgeToEdge.enable(this, SystemBarStyle.dark(Color.TRANSPARENT));
        setContentView(layoutRes);
        MaterialToolbar toolbar = findViewById(R.id.toolbar);
        setSupportActionBar(toolbar);
        if (showUp && getSupportActionBar() != null) {
            getSupportActionBar().setDisplayHomeAsUpEnabled(true);
        }
        ViewCompat.setOnApplyWindowInsetsListener(findViewById(R.id.root), (root, insets) -> {
            Insets bars = insets.getInsets(WindowInsetsCompat.Type.systemBars()
                    | WindowInsetsCompat.Type.displayCutout());
            Insets ime = insets.getInsets(WindowInsetsCompat.Type.ime());
            toolbar.setPadding(0, bars.top, 0, 0);
            root.setPadding(bars.left, 0, bars.right, Math.max(bars.bottom, ime.bottom));
            return WindowInsetsCompat.CONSUMED;
        });
    }
}
